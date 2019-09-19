import json
from os import isatty
import re
import termios
import tty
import signal
import sys

from ansible.errors import AnsibleError, AnsibleUndefinedVariable
from ansible.module_utils.six import iteritems, string_types, PY3
from ansible.module_utils._text import to_text, to_native
from ansible.module_utils.parsing.convert_bool import boolean
from ansible.plugins.action import ActionBase
from ansible.utils.display import Display
from ansible.utils.vars import isidentifier
from ansible.plugins.action import ActionBase

import ansible.constants as C


display = Display()
try:
    import curses

    # Nest the try except since curses.error is not available if curses did not import
    try:
        curses.setupterm()
        HAS_CURSES = True
    except curses.error:
        HAS_CURSES = False
except ImportError:
    HAS_CURSES = False

if HAS_CURSES:
    MOVE_TO_BOL = curses.tigetstr('cr')
    CLEAR_TO_EOL = curses.tigetstr('el')
else:
    MOVE_TO_BOL = b'\r'
    CLEAR_TO_EOL = b'\x1b[K'

def clear_line(stdout):
    stdout.write(b'\x1b[%s' % MOVE_TO_BOL)
    stdout.write(b'\x1b[%s' % CLEAR_TO_EOL)


class InnerFailure(Exception):
    def __init__(self, result):
        self.result = result
        super().__init__()


class ActionModule(ActionBase):
    TRANSFERS_FILES = False
    TRUES = ('true', 'yes', '1')
    FALSES = ('false', 'no', '0')

    def ask(self, name, save=True):
        var = self.get_var(name)
        value = self.prompt(var)
        if not value and 'default' in var:
            value = self.render(var['default'])
        else:
            while not self.validate(var, value):
                value = self.prompt(var, value)
        value = self.sanitize(var, value)
        self.task_vars[name] = value
        self.facts[name] = value
        if save:
            self.save()
        return value

    def sanitize(self, var, value):
        if 'choices' in var:
            return var['choices'][value]

        if 'type' in var:
            if var['type'] in ('bool', 'boolean'):
                return True if str(value).lower() in self.TRUES else False

        return value

    def validate(self, var, value):
        if 'regexp' in var:
            return re.match(var['regexp'], value)

        if 'type' in var:
            if var['type'] == 'bool':
                return value in (self.TRUES + self.FALSES)
            elif var['type'] == 'path':
                return value.startswith('/')
            elif var['type'] == 'email':
                return '@' in value  # todo: regexp
            elif var['type'] == 'hostname':
                # todo: use this regexp
                # https://github.com/ruby/ruby/blob/trunk/lib/uri/rfc3986_parser.rb#L6
                return '/' not in value

        if 'choices' in var:
            return value in var['choices'].keys()

        return True

    def run(self, tmp=None, task_vars=None):
        result = super(ActionModule, self).run(tmp, task_vars)
        del tmp  # tmp no longer has any effect

        self.task_vars = task_vars or dict(
            ansible_facts=dict(
                ansible_local=dict()
            )
        )

        try:
            return self._run(result)
        except InnerFailure as e:
            return e.result

    def _run(self, result):
        self.fact_name = None  # let get_fact_name dependencies use fact_name
        result = self._execute_module(
            module_name='setup',
            module_args=dict(
                gather_subset=[
                    '!all',
                    '!any',
                    'facter',
                ]
            ),
            task_vars=self.task_vars
        )
        self.ansible_local = result['ansible_facts']['ansible_local']
        self.facts = dict()
        self.fact_name = self.get_fact_name()
        rolevars = self.ansible_local[self.fact_name]
        self.facts.update(rolevars)
        self.task_vars.update(rolevars)

        for var in self.task_vars.get('remember', {}):
            display.vv(f'Now dealing with {var["name"]}')
            if 'when' in var:
                when = self.render('{{ ' + var['when'] + ' }}')
                if not when:
                    display.v(f'{var["name"]}.when: {var["when"]}={when}')
                    continue

            force = False
            forceask = self.task_vars.get('forceask', '').split(',')
            force = var['name'] in forceask or forceask in ('*', 'all')
            if (
                'state' in self.task_vars.get('remember_extra', {})
                and self.task_vars['remember_extra']['state'] == 'success'
            ):
                force = False
            elif force or var['name'] not in self.task_vars:
                self.ask(var['name'])
            else:
                self.facts[var['name']] = self.task_vars[var['name']]
                self.task_vars[var['name']] = self.task_vars[var['name']]
            display.v(f'Value for {var["name"]}: {self.task_vars[var["name"]]}')

        for key, value in self._task.args.get('extra', {}).items():
            self.facts[key] = value

        if 'state' in self._task.args:
            self.facts['state'] = self._task.args['state']

        self.save()

        result['changed'] = False
        result['ansible_facts'] = self.facts
        result['_ansible_facts_cacheable'] = True
        return result

    def get_fact_name(self):
        if 'remember_fact' not in self.task_vars:
            name = self.task_vars['role_name']
            if '/' in name:
                name = role_name.split('/')[-1]
        else:
            name = self.render(self.task_vars['remember_fact'])
        return name.replace('.', '_').replace('/', '_')

    def render(self, value):
        if isinstance(value, str):
            value = value.replace('j2((', '{{').replace('))', '}}')

        tries = 30
        while tries:
            try:
                return self._templar.template(value)
            except AnsibleUndefinedVariable as exc:
                m = re.match("'([^)]+)' is undefined", exc.message)
                if m:
                    self.ask(m.group(1), save=False)
            tries -= 1
        raise Exception('Could not render: ' + value)

    def get_var(self, name):
        for var in self.task_vars.get('remember', []):
            if not isinstance(var, dict):
                raise Exception(f'{var} is not a dict')

            if 'name' not in var:
                raise Exception(f'{var} has no name')

            if var['name'] == name:
                if name in self.hostvals:
                    var['hostval'] = self.hostvals[name]
                return var

        raise Exception(f'{name} not found in vars')

    @property
    def hostvals(self):
        if not self.fact_name:
            return {}

        return self.ansible_local.get(self.fact_name, {})

    @property
    def fact_content(self):
        return '\n'.join([
            '#!/bin/sh',
            'cat <<EOF',
            json.dumps(
                self.facts,
                sort_keys=True,
                indent=4
            ),
            'EOF',
        ])

    def save(self):
        result = self._execute_module(
            module_name='file',
            module_args=dict(
                path='/etc/ansible/facts.d',
                state='directory'
            ),
            task_vars=self.task_vars
        )
        if result.get('failed'):
            raise InnerFailure(result)

        display.v(
            f'Saving to /etc/ansible/facts.d/{self.fact_name}.fact:\n'
            + self.fact_content
        )

        new_task = self._task.copy()
        new_task.args = dict(
            content=self.fact_content,
            dest=f'/etc/ansible/facts.d/{self.fact_name}.fact',
            mode='0755',
            owner='root'
        )
        copy_action = self._shared_loader_obj.action_loader.get(
            'copy',
            task=new_task,
            connection=self._connection,
            play_context=self._play_context,
            loader=self._loader,
            templar=self._templar,
            shared_loader_obj=self._shared_loader_obj
        )
        result = copy_action.run(task_vars=self.task_vars)

        if result.get('failed'):
            raise InnerFailure(result)

    def prompt(self, var, invalid=None):
        echo = True
        echo_prompt = ''
        user_input = b''
        prompt = self.render(var['question'])
        if var['name'] in self.task_vars:
            prompt += ' Current: ' + self.task_vars[var['name']]

        if 'type' in var:
            prompt += f' (type: {var["type"]})'

        if 'default' in var:
            prompt += f' (default: {self.render(var["default"])})'

        if 'choices' in var:
            prompt += '\n\nSelect one of the following choices by typing the'
            prompt += ' word on the left of the parenthesis:'
            for key, value in var['choices'].items():
                prompt += f'\n{key}) {value}'

        if invalid:
            prompt += '\nYour answer did not validate: ' + invalid

        stdin_fd = None
        old_settings = None
        try:
            display.display(prompt)

            # save the attributes on the existing (duped) stdin so
            # that we can restore them later after we set raw mode
            stdin_fd = None
            stdout_fd = None
            try:
                if PY3:
                    stdin = self._connection._new_stdin.buffer
                    stdout = sys.stdout.buffer
                else:
                    stdin = self._connection._new_stdin
                    stdout = sys.stdout
                stdin_fd = stdin.fileno()
                stdout_fd = stdout.fileno()
            except (ValueError, AttributeError):
                # ValueError: someone is using a closed file descriptor as stdin
                # AttributeError: someone is using a null file descriptor as stdin on windoez
                stdin = None

            if stdin_fd is not None:
                if isatty(stdin_fd):
                    # grab actual Ctrl+C sequence
                    try:
                        intr = termios.tcgetattr(stdin_fd)[6][termios.VINTR]
                    except Exception:
                        # unsupported/not present, use default
                        intr = b'\x03'  # value for Ctrl+C

                    # get backspace sequences
                    try:
                        backspace = termios.tcgetattr(stdin_fd)[6][termios.VERASE]
                    except Exception:
                        backspace = [b'\x7f', b'\x08']

                    old_settings = termios.tcgetattr(stdin_fd)
                    tty.setraw(stdin_fd)

                    # Only set stdout to raw mode if it is a TTY. This is needed when redirecting
                    # stdout to a file since a file cannot be set to raw mode.
                    if isatty(stdout_fd):
                        tty.setraw(stdout_fd)

                    # Only echo input if no timeout is specified
                    new_settings = termios.tcgetattr(stdin_fd)
                    new_settings[3] = new_settings[3] | termios.ECHO
                    termios.tcsetattr(stdin_fd, termios.TCSANOW, new_settings)

                    # flush the buffer to make sure no previous key presses
                    # are read in below
                    termios.tcflush(stdin, termios.TCIFLUSH)

            while True:
                try:
                    if stdin_fd is not None:

                        key_pressed = stdin.read(1)

                        if key_pressed == intr:  # value for Ctrl+C
                            clear_line(stdout)
                            raise KeyboardInterrupt

                    if stdin_fd is None or not isatty(stdin_fd):
                        display.warning("Not waiting for response to prompt as stdin is not interactive")
                        break

                    # read key presses and act accordingly
                    if key_pressed in (b'\r', b'\n'):
                        clear_line(stdout)
                        break
                    elif key_pressed in backspace:
                        # delete a character if backspace is pressed
                        user_input = user_input[:-1]
                        clear_line(stdout)
                        if echo:
                            stdout.write(user_input)
                        stdout.flush()
                    else:
                        user_input += key_pressed

                except KeyboardInterrupt:
                    signal.alarm(0)
                    clear_line(stdout)
                    raise AnsibleError('user requested abort!')

        finally:
            # cleanup and save some information
            # restore the old settings for the duped stdin stdin_fd
            if not(None in (stdin_fd, old_settings)) and isatty(stdin_fd):
                termios.tcsetattr(stdin_fd, termios.TCSADRAIN, old_settings)

        return to_text(user_input, errors='surrogate_or_strict')
