# pylontech_emulator/__init__.py — ESPHome component integration
# v5.0.0 — Enterprise edition with temperature & query counter support

import esphome.codegen as cg
import esphome.config_validation as cv
from esphome.components import uart, sensor
from esphome.const import CONF_ID

DEPENDENCIES = ["uart"]
AUTO_LOAD = ["sensor"]

CONF_SOC_SENSOR = "soc_sensor"
CONF_VOLTAGE_SENSOR = "voltage_sensor"
CONF_CURRENT_SENSOR = "current_sensor"
CONF_TEMP_SENSOR = "temp_sensor"
CONF_QUERY_COUNT_SENSOR = "query_count_sensor"
CONF_FLOW_CONTROL_PIN = "flow_control_pin"

pylontech_emulator_ns = cg.esphome_ns.namespace("pylontech_emulator")
PylontechEmulator = pylontech_emulator_ns.class_(
    "PylontechEmulator", cg.Component, uart.UARTDevice
)

CONFIG_SCHEMA = (
    cv.Schema(
        {
            cv.GenerateID(): cv.declare_id(PylontechEmulator),
            cv.Required(CONF_SOC_SENSOR): cv.use_id(sensor.Sensor),
            cv.Required(CONF_VOLTAGE_SENSOR): cv.use_id(sensor.Sensor),
            cv.Required(CONF_CURRENT_SENSOR): cv.use_id(sensor.Sensor),
            cv.Optional(CONF_TEMP_SENSOR): cv.use_id(sensor.Sensor),
            cv.Optional(CONF_QUERY_COUNT_SENSOR): cv.use_id(sensor.Sensor),
            cv.Optional(CONF_FLOW_CONTROL_PIN, default=-1): cv.int_,
        }
    )
    .extend(uart.UART_DEVICE_SCHEMA)
    .extend(cv.COMPONENT_SCHEMA)
)


async def to_code(config):
    var = cg.new_Pvariable(config[CONF_ID])
    await cg.register_component(var, config)
    await uart.register_uart_device(var, config)

    soc = await cg.get_variable(config[CONF_SOC_SENSOR])
    cg.add(var.set_soc_sensor(soc))

    voltage = await cg.get_variable(config[CONF_VOLTAGE_SENSOR])
    cg.add(var.set_voltage_sensor(voltage))

    current = await cg.get_variable(config[CONF_CURRENT_SENSOR])
    cg.add(var.set_current_sensor(current))

    if CONF_TEMP_SENSOR in config:
        temp = await cg.get_variable(config[CONF_TEMP_SENSOR])
        cg.add(var.set_temp_sensor(temp))

    if CONF_QUERY_COUNT_SENSOR in config:
        qc = await cg.get_variable(config[CONF_QUERY_COUNT_SENSOR])
        cg.add(var.set_query_count_sensor(qc))

    cg.add(var.set_flow_control_pin(config[CONF_FLOW_CONTROL_PIN]))
