# Virtual Pins support
#
# Copyright (C) 2023 Pedro Lamas <pedrolamas@gmail.com>
#
# This file may be distributed under the terms of the MIT license.

import logging
from . import output_pin

class VirtualPins:
    def __init__(self, config):
        self._printer = config.get_printer()
        self._ppins = self._printer.lookup_object('pins')
        self._ppins.register_chip('virtual_pin', self)
        output_pin.lookup_template_eval(config)  # ensure template eval is loaded
        self._start_values = {}
        start_values = config.getlists("start_values", (), seps=('=', ','), count=2)
        for name, value in start_values:
            try:
                self._start_values[name] = float(value)
            except ValueError:
                raise config.error("start_values entry for pin '%s' is not a valid number: '%s'" % (name, value))
        self._pins = {}
        self._oid_count = 0
        self._config_callbacks = []
        # Button tracking infrastructure
        self._buttons = {}  # oid -> Button
        self._response_handlers = {}  # (msg_name, oid) -> callback
        self._printer.register_event_handler("klippy:connect",
                                             self.handle_connect)

    def handle_connect(self):
        for cb in self._config_callbacks:
            cb()

    def _poll_buttons(self, eventtime, oid):
        if oid not in self._buttons:
            return self._printer.get_reactor().NEVER

        button = self._buttons[oid]
        handler_key = ('buttons_state', oid)

        if handler_key not in self._response_handlers:
            return self._printer.get_reactor().NEVER

        button_state = 0
        for pos, pin_name in enumerate(button.pins):
            if pin_name and pin_name in self._pins:
                state = int(self._pins[pin_name].get_digital())
                if state:
                    button_state |= (1 << pos)

        # Report raw pin states like the MCU firmware does; stock buttons.py
        # applies button.invert itself in handle_buttons_state, so inverting
        # here too would cancel out and break inverted buttons.

        params = {
            'oid': oid,
            'ack_count': button.ack_count & 0xff,  # Keep it as 8-bit
            'state': bytearray([button_state]),
            '#receive_time': eventtime
        }

        callback = self._response_handlers[handler_key]
        callback(params)

        return eventtime + 0.01

    def setup_pin(self, pin_type, pin_params):
        pin_classes = {
            'digital_out': DigitalOutVirtualPin,
            'pwm': PwmVirtualPin,
            'adc': AdcVirtualPin,
            'endstop': EndstopVirtualPin,
            'digital_in': DigitalInVirtualPin,
        }
        pin_class = pin_classes.get(pin_type)
        if pin_class is None:
            raise self._ppins.error("unable to create virtual pin of type %s" % (
                pin_type,))
        name = pin_params['pin']
        if name in self._pins:
            existing = self._pins[name]
            if not isinstance(existing, pin_class):
                raise self._ppins.error(
                    "virtual pin '%s' is already in use as a different type" % (
                        name,))
            return existing
        pin = pin_class(self, pin_params, self._start_values.get(name))
        self._pins[name] = pin
        return pin

    def create_oid(self):
        self._oid_count += 1
        return self._oid_count - 1

    def register_config_callback(self, cb):
        self._config_callbacks.append(cb)

    def _parse_cmd(self, cmd):
        parsed = {}
        parts = cmd.split()
        for part in parts[1:]:
            if '=' in part:
                key, value = part.split('=', 1)
                parsed[key] = value
        return parsed

    def add_config_cmd(self, cmd, is_init=False, on_restart=False):
        if cmd.startswith("config_buttons "):
            # Parse: config_buttons oid=%d button_count=%d
            parsed = self._parse_cmd(cmd)
            oid = int(parsed.get('oid')) if 'oid' in parsed else None
            button_count = int(parsed.get('button_count', 0))
            if button_count > 8:
                raise self._ppins.error("Max of 8 buttons per oid")
            if oid is not None:
                self._buttons[oid] = Button(button_count)

        elif cmd.startswith("buttons_add "):
            # Parse: buttons_add oid=%d pos=%d pin=%s pull_up=%d
            parsed = self._parse_cmd(cmd)
            oid = int(parsed.get('oid')) if 'oid' in parsed else None
            pos = int(parsed.get('pos')) if 'pos' in parsed else None
            pin = parsed.get('pin')
            if oid in self._buttons and pos is not None and pin is not None:
                button = self._buttons[oid]
                if pos >= button.button_count:
                    raise self._ppins.error(
                        "Set button past maximum button count")
                button.pins[pos] = pin
                pin_params = {
                    'pin': pin,
                    'pullup': int(parsed.get('pull_up', 0)),
                    'invert': 0
                }
                self.setup_pin('digital_in', pin_params)

        elif cmd.startswith("buttons_query "):
            # Parse: buttons_query oid=%d clock=%d rest_ticks=%d retransmit_count=%d invert=%d
            parsed = self._parse_cmd(cmd)
            oid = int(parsed.get('oid')) if 'oid' in parsed else None
            if oid in self._buttons:
                button = self._buttons[oid]
                button.invert = int(parsed.get('invert', 0))
                button.rest_ticks = int(parsed.get('rest_ticks', 0))
                button.retransmit_count = int(parsed.get('retransmit_count', 0))

    def get_query_slot(self, oid):
        return 0

    def seconds_to_clock(self, time):
        return 0

    def get_printer(self):
        return self._printer

    def register_serial_response(self, cb, msg, oid=None):
        msg = msg.split()[0]
        if msg == "buttons_state" and oid is not None:
            self._response_handlers[(msg, oid)] = cb
            if oid in self._buttons and self._buttons[oid].timer is None:
                reactor = self._printer.get_reactor()
                self._buttons[oid].timer = reactor.register_timer(
                    lambda et: self._poll_buttons(et, oid),
                    reactor.monotonic() + 0.01)
        return VirtualAsyncResponseWrapper(lambda: self._unregister_response_wrapper(msg, oid))

    def _unregister_response_wrapper(self, msg, oid):
        self._response_handlers.pop((msg, oid), None)
        if msg == "buttons_state" and oid in self._buttons:
            button = self._buttons[oid]
            if button.timer is not None:
                self._printer.get_reactor().unregister_timer(button.timer)
                button.timer = None

    def _increment_button_send_count(self, oid, count):
        if oid in self._buttons:
            self._buttons[oid].ack_count += count

    def alloc_command_queue(self):
        pass

    def lookup_command(self, msgformat, cq=None):
        if msgformat.startswith("buttons_ack "):
            return VirtualButtonCommand(self._increment_button_send_count)
        return VirtualCommand()

    def lookup_query_command(self, msgformat, respformat, oid=None,
                             cq=None, is_async=False):
        return VirtualCommandQuery(respformat, oid)

    def get_enumerations(self):
        return {}

    def print_time_to_clock(self, print_time):
        return 0

    def estimated_print_time(self, eventtime):
        return 0

    def request_move_queue_slot(self):
        pass

    def get_status(self, eventtime):
        return {
            'pins': {
                name : pin.get_status(eventtime)
                    for name, pin in self._pins.items()
            }
        }

class VirtualCommand:
    def send(self, data=(), minclock=0, reqclock=0):
        pass

    def get_command_tag(self):
        pass

class VirtualButtonCommand:
    def __init__(self, on_send):
        self._on_send = on_send

    def send(self, data=(), minclock=0, reqclock=0):
        if len(data) >= 2:
            oid = data[0]
            count = data[1]
            self._on_send(oid, count)

    def get_command_tag(self):
        pass

class VirtualAsyncResponseWrapper:
    def __init__(self, on_unregister):
        self._on_unregister = on_unregister

    def unregister(self):
        self._on_unregister()

class VirtualCommandQuery:
    def __init__(self, respformat, oid):
        entries = respformat.split()
        self._response = {}
        for entry in entries[1:]:
            key, _ = entry.split('=')
            self._response[key] = oid if key == 'oid' else 1

    def send(self, data=(), minclock=0, reqclock=0):
        return self._response

    def send_with_preface(self, preface_cmd, preface_data=(), data=(),
                          minclock=0, reqclock=0):
        return self._response

class VirtualPin:
    def __init__(self, mcu, pin_params, start_value):
        self._mcu = mcu
        self._name = pin_params['pin']
        self._pullup = pin_params['pullup']
        self._invert = pin_params['invert']
        self._value = 0.
        if start_value is not None:
            self._value = start_value
        self._printer = self._mcu.get_printer()
        self._reactor = self._printer.get_reactor()
        self._printer.register_event_handler("klippy:ready", self._handle_ready)
        self._real_mcu = self._printer.lookup_object('mcu')
        gcode = self._printer.lookup_object('gcode')
        gcode.register_mux_command("SET_VIRTUAL_PIN", "PIN", self._name,
                                   self.cmd_SET_VIRTUAL_PIN,
                                   desc=self.cmd_SET_VIRTUAL_PIN_help)

    def _handle_ready(self):
        self.timer_handler = self._reactor.register_timer(
            self._set_virtual_pin_timer_event, self._reactor.NEVER)

    def _set_virtual_pin_timer_event(self, eventtime):
        self._value = self._delayed_value
        return self._reactor.NEVER

    def _template_update(self, text):
        try:
            value = float(text)
        except ValueError:
            logging.exception("output_pin template render error")
            value = 0.
        self._value = value

    cmd_SET_VIRTUAL_PIN_help = "Set the value of an output pin"
    def cmd_SET_VIRTUAL_PIN(self, gcmd):
        value = gcmd.get_float('VALUE', None, minval=0., maxval=1.)
        template = gcmd.get('TEMPLATE', None)
        if (value is None) == (template is None):
            raise gcmd.error("SET_PIN command must specify VALUE or TEMPLATE")
        if template is not None:
            template_eval = self._printer.lookup_object('template_evaluator')
            template_eval.set_template(gcmd, self._template_update)
            return
        delay = gcmd.get_float('DELAY', 0., minval=0.)
        if (delay > 0.):
            self._delayed_value = value
            self._reactor.update_timer(self.timer_handler,
                                       self._reactor.monotonic() + delay)
        else:
            self._reactor.update_timer(self.timer_handler,
                                       self._reactor.NEVER)
            self._value = value

    def get_mcu(self):
        return self._real_mcu

class DigitalOutVirtualPin(VirtualPin):
    def __init__(self, mcu, pin_params, start_value):
        VirtualPin.__init__(self, mcu, pin_params, start_value)

    def setup_max_duration(self, max_duration):
        pass

    def setup_start_value(self, start_value, shutdown_value):
        self._set_value(start_value)

    def set_digital(self, print_time, value):
        self._set_value(value)

    def get_status(self, eventtime):
        return {
            'value': self._value,
            'type': 'digital_out'
        }

    def _set_value(self, value):
        self._value = (not not value) ^ self._invert

class PwmVirtualPin(VirtualPin):
    def __init__(self, mcu, pin_params, start_value):
        VirtualPin.__init__(self, mcu, pin_params, start_value)

    def setup_max_duration(self, max_duration):
        pass

    def setup_start_value(self, start_value, shutdown_value):
        self._set_value(start_value)

    def setup_cycle_time(self, cycle_time, hardware_pwm=False):
        pass

    def set_pwm(self, print_time, value, cycle_time=None):
        self._set_value(value)

    def get_status(self, eventtime):
        return {
            'value': self._value,
            'type': 'pwm'
        }

    def _set_value(self, value):
        if self._invert:
            value = 1. - value
        self._value = value

class AdcVirtualPin(VirtualPin):
    def __init__(self, mcu, pin_params, start_value):
        VirtualPin.__init__(self, mcu, pin_params, start_value)
        self._callback = None
        self._min_sample = 0.
        self._max_sample = 0.
        self._printer.register_event_handler("klippy:connect",
                                            self.handle_connect)

    def handle_connect(self):
        self._reactor.register_timer(self._raise_callback,
                                     self._reactor.monotonic() + 0.5)

    def setup_adc_callback(self, callback):
        self._callback = callback

    def setup_adc_sample(self, report_time, sample_time=0., sample_count=1,
                         batch_num=1, minval=0., maxval=1.,
                         range_check_count=0):
        self._sample_time = sample_time
        self._min_sample = minval
        self._max_sample = maxval

    def _raise_callback(self, eventtime):
        sample_range = self._max_sample - self._min_sample
        value = (self._value * sample_range) + self._min_sample
        if self._callback is not None:
            self._callback([(eventtime, value)])
        return eventtime + self._sample_time

    def get_status(self, eventtime):
        return {
            'value': self._value,
            'type': 'adc'
        }

class EndstopVirtualPin(VirtualPin):
    RETRY_QUERY = 0.001  # pin poll interval during a homing move

    def __init__(self, mcu, pin_params, start_value):
        VirtualPin.__init__(self, mcu, pin_params, start_value)
        self._steppers = []
        self._trigger_completion = None
        self._triggered = True
        self._home_timer = None

    def add_stepper(self, stepper):
        self._steppers.append(stepper)

    def query_endstop(self, print_time):
        return (not not self._value) ^ self._invert

    def home_start(self, print_time, sample_time, sample_count, rest_time,
                   triggered=True):
        if self._home_timer is not None:
            self._reactor.unregister_timer(self._home_timer)
            self._home_timer = None
        self._triggered = triggered
        self._trigger_completion = self._reactor.completion()
        self._home_timer = self._reactor.register_timer(
            self._home_check, self._reactor.monotonic() + sample_time)
        return self._trigger_completion

    def _home_check(self, eventtime):
        if self.query_endstop(eventtime) == (not not self._triggered):
            self._trigger_completion.complete(True)
            return self._reactor.NEVER
        return eventtime + self.RETRY_QUERY

    def home_wait(self, home_end_time):
        if self._home_timer is not None:
            self._reactor.unregister_timer(self._home_timer)
            self._home_timer = None
        if self._trigger_completion is None:
            return 0.
        # In file-output mode (klippy batch/simulation) the reactor is not
        # pumped during the drip move, so the poll timer never fires; mirror
        # the stock MCU endstop (mcu.py) and report a successful trigger.
        if self._real_mcu.is_fileoutput():
            self._trigger_completion = None
            return home_end_time
        triggered = self._trigger_completion.test()
        self._trigger_completion = None
        return home_end_time if triggered else 0.

    def get_steppers(self):
        return list(self._steppers)

    def get_status(self, eventtime):
        return {
            'value': self._value,
            'type': 'endstop'
        }

class DigitalInVirtualPin(VirtualPin):
    def __init__(self, mcu, pin_params, start_value):
        VirtualPin.__init__(self, mcu, pin_params, start_value)

    def get_digital(self):
        return (not not self._value) ^ self._invert

    def get_status(self, eventtime):
        return {
            'value': self._value,
            'type': 'digital_in'
        }

class Button:
    def __init__(self, button_count):
        self.button_count = button_count
        self.pins = [None] * button_count
        self.invert = 0
        self.rest_ticks = 0
        self.retransmit_count = 0
        self.ack_count = 0
        self.timer = None

def load_config(config):
    return VirtualPins(config)
