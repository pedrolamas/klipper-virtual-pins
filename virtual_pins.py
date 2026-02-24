# Virtual Pins support
#
# Copyright (C) 2023 Pedro Lamas <pedrolamas@gmail.com>
#
# This file may be distributed under the terms of the GNU GPLv3 license.

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
        self._printer.register_event_handler("klippy:connect",
                                             self.handle_connect)

    def handle_connect(self):
        for cb in self._config_callbacks:
            cb()

    def setup_pin(self, pin_type, pin_params):
        name = pin_params['pin']
        if name in self._pins:
            return self._pins[name]
        start_value = self._start_values.get(name)
        if pin_type == 'digital_out':
            pin = DigitalOutVirtualPin(self, pin_params, start_value)
        elif pin_type == 'pwm':
            pin = PwmVirtualPin(self, pin_params, start_value)
        elif pin_type == 'adc':
            pin = AdcVirtualPin(self, pin_params, start_value)
        elif pin_type == 'endstop':
            pin = EndstopVirtualPin(self, pin_params, start_value)
        else:
            raise self._ppins.error("unable to create virtual pin of type %s" % (
                pin_type,))
        self._pins[name] = pin
        return pin

    def create_oid(self):
        self._oid_count += 1
        return self._oid_count - 1

    def register_config_callback(self, cb):
        self._config_callbacks.append(cb)

    def add_config_cmd(self, cmd, is_init=False, on_restart=False):
        pass

    def get_query_slot(self, oid):
        return 0

    def seconds_to_clock(self, time):
        return 0

    def get_printer(self):
        return self._printer

    def register_response(self, cb, msg, oid=None):
        pass

    def alloc_command_queue(self):
        pass

    def lookup_command(self, msgformat, cq=None):
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
    def __init__(self, mcu, pin_params, start_value):
        VirtualPin.__init__(self, mcu, pin_params, start_value)
        self._steppers = []

    def add_stepper(self, stepper):
        self._steppers.append(stepper)

    def query_endstop(self, print_time):
        return (not not self._value) ^ self._invert

    def home_start(self, print_time, sample_time, sample_count, rest_time,
                   triggered=True):
        completion = self._reactor.completion()
        completion.complete(True)
        return completion

    def home_wait(self, home_end_time):
        return 1

    def get_steppers(self):
        return list(self._steppers)

    def get_status(self, eventtime):
        return {
            'value': self._value,
            'type': 'endstop'
        }

def load_config(config):
    return VirtualPins(config)
