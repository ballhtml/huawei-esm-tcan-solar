import esphome.codegen as cg
import esphome.config_validation as cv
from esphome.components import sensor, time as time_
from esphome.components.esp32 import include_builtin_idf_component, require_fatfs
from esphome.const import CONF_ID, CONF_UPDATE_INTERVAL

include_builtin_idf_component("fatfs")
include_builtin_idf_component("wear_levelling")
include_builtin_idf_component("sdmmc")
require_fatfs()

AUTO_LOAD = ["sensor", "time"]

CONF_CS_PIN = "cs_pin"
CONF_MOSI_PIN = "mosi_pin"
CONF_MISO_PIN = "miso_pin"
CONF_CLK_PIN = "clk_pin"
CONF_HTTP_PORT = "http_port"

CONF_VOLTAGE_SENSOR = "voltage_sensor"
CONF_CURRENT_SENSOR = "current_sensor"
CONF_POWER_SENSOR = "power_sensor"
CONF_SOC_SENSOR = "soc_sensor"
CONF_TEMP_SENSOR = "temp_sensor"

CONF_PACK1_SOC = "pack1_soc"
CONF_PACK1_V = "pack1_v"
CONF_PACK1_I = "pack1_i"

CONF_PACK2_SOC = "pack2_soc"
CONF_PACK2_V = "pack2_v"
CONF_PACK2_I = "pack2_i"

CONF_PACK3_SOC = "pack3_soc"
CONF_PACK3_V = "pack3_v"
CONF_PACK3_I = "pack3_i"

CONF_PACK4_SOC = "pack4_soc"
CONF_PACK4_V = "pack4_v"
CONF_PACK4_I = "pack4_i"

CONF_INVERTER_QUERIES = "inverter_queries"
CONF_TIME_ID = "time_id"

sd_logger_ns = cg.esphome_ns.namespace("sd_logger")
SDLogger = sd_logger_ns.class_("SDLogger", cg.PollingComponent)

CONFIG_SCHEMA = (
    cv.Schema(
        {
            cv.GenerateID(): cv.declare_id(SDLogger),
            cv.Optional(CONF_UPDATE_INTERVAL, default="10s"): cv.update_interval,
            cv.Optional(CONF_CS_PIN, default=13): cv.int_,
            cv.Optional(CONF_MOSI_PIN, default=15): cv.int_,
            cv.Optional(CONF_MISO_PIN, default=2): cv.int_,
            cv.Optional(CONF_CLK_PIN, default=14): cv.int_,
            cv.Optional(CONF_HTTP_PORT, default=8080): cv.int_,
            cv.Optional(CONF_TIME_ID): cv.use_id(time_.RealTimeClock),
            cv.Optional(CONF_VOLTAGE_SENSOR): cv.use_id(sensor.Sensor),
            cv.Optional(CONF_CURRENT_SENSOR): cv.use_id(sensor.Sensor),
            cv.Optional(CONF_POWER_SENSOR): cv.use_id(sensor.Sensor),
            cv.Optional(CONF_SOC_SENSOR): cv.use_id(sensor.Sensor),
            cv.Optional(CONF_TEMP_SENSOR): cv.use_id(sensor.Sensor),
            cv.Optional(CONF_PACK1_SOC): cv.use_id(sensor.Sensor),
            cv.Optional(CONF_PACK1_V): cv.use_id(sensor.Sensor),
            cv.Optional(CONF_PACK1_I): cv.use_id(sensor.Sensor),
            cv.Optional(CONF_PACK2_SOC): cv.use_id(sensor.Sensor),
            cv.Optional(CONF_PACK2_V): cv.use_id(sensor.Sensor),
            cv.Optional(CONF_PACK2_I): cv.use_id(sensor.Sensor),
            cv.Optional(CONF_PACK3_SOC): cv.use_id(sensor.Sensor),
            cv.Optional(CONF_PACK3_V): cv.use_id(sensor.Sensor),
            cv.Optional(CONF_PACK3_I): cv.use_id(sensor.Sensor),
            cv.Optional(CONF_PACK4_SOC): cv.use_id(sensor.Sensor),
            cv.Optional(CONF_PACK4_V): cv.use_id(sensor.Sensor),
            cv.Optional(CONF_PACK4_I): cv.use_id(sensor.Sensor),
            cv.Optional(CONF_INVERTER_QUERIES): cv.use_id(sensor.Sensor),
        }
    )
    .extend(cv.COMPONENT_SCHEMA)
)


async def to_code(config):
    include_builtin_idf_component("fatfs")
    include_builtin_idf_component("wear_levelling")
    include_builtin_idf_component("sdmmc")
    require_fatfs()

    var = cg.new_Pvariable(config[CONF_ID])
    await cg.register_component(var, config)

    cg.add(var.set_pins(config[CONF_CS_PIN], config[CONF_MOSI_PIN], config[CONF_MISO_PIN], config[CONF_CLK_PIN]))
    cg.add(var.set_http_port(config[CONF_HTTP_PORT]))

    if CONF_TIME_ID in config:
        time_var = await cg.get_variable(config[CONF_TIME_ID])
        cg.add(var.set_time(time_var))

    for key, setter in [
        (CONF_VOLTAGE_SENSOR, "set_voltage_sensor"),
        (CONF_CURRENT_SENSOR, "set_current_sensor"),
        (CONF_POWER_SENSOR, "set_power_sensor"),
        (CONF_SOC_SENSOR, "set_soc_sensor"),
        (CONF_TEMP_SENSOR, "set_temp_sensor"),
        (CONF_PACK1_SOC, "set_pack1_soc"),
        (CONF_PACK1_V, "set_pack1_v"),
        (CONF_PACK1_I, "set_pack1_i"),
        (CONF_PACK2_SOC, "set_pack2_soc"),
        (CONF_PACK2_V, "set_pack2_v"),
        (CONF_PACK2_I, "set_pack2_i"),
        (CONF_PACK3_SOC, "set_pack3_soc"),
        (CONF_PACK3_V, "set_pack3_v"),
        (CONF_PACK3_I, "set_pack3_i"),
        (CONF_PACK4_SOC, "set_pack4_soc"),
        (CONF_PACK4_V, "set_pack4_v"),
        (CONF_PACK4_I, "set_pack4_i"),
        (CONF_INVERTER_QUERIES, "set_inverter_queries"),
    ]:
        if key in config:
            s = await cg.get_variable(config[key])
            cg.add(getattr(var, setter)(s))
