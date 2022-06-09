"""
Support for JemenaOutlook.
Get data from 'Jemena Energy Outlook - Your Electricity Use' page/s:
https://electricityoutlook.jemena.com.au/electricityView/index
For more details about this platform, please refer to the documentation at
https://github.com/mvandersteen/ha-jemenaoutlook
"""
import logging
from datetime import timedelta
import json

import re
from bs4 import BeautifulSoup
import requests

import locale

import http.client as http_client

import voluptuous as vol

from homeassistant.components.sensor import (
    PLATFORM_SCHEMA,
    SensorDeviceClass,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.const import (
    CONF_USERNAME,
    CONF_PASSWORD,
    CONF_NAME,
    CONF_MONITORED_VARIABLES,
    ENERGY_KILO_WATT_HOUR,
    CURRENCY_DOLLAR,
    PERCENTAGE,
)
from homeassistant.helpers.entity import Entity
from homeassistant.util import Throttle
import homeassistant.helpers.config_validation as cv

REQUIREMENTS = ["beautifulsoup4==4.6.0"]

http_client.HTTPConnection.debuglevel = 1

logging.basicConfig(level=logging.DEBUG)
_LOGGER = logging.getLogger(__name__)
requests_log = logging.getLogger("requests.packages.urllib3")
requests_log.setLevel(logging.DEBUG)
requests_log.propagate = True

MIN_TIME_BETWEEN_UPDATES = timedelta(hours=24)
SCAN_INTERVAL = timedelta(hours=24)

REQUESTS_TIMEOUT = 15

HOST = "https://electricityoutlook.jemena.com.au"
HOME_URL = "{}/login/index".format(HOST)
PERIOD_URL = "{}/electricityView/period".format(HOST)

DEFAULT_NAME = "JemenaOutlook"

SENSOR_TYPES = {
    "yesterday_user_type": [
        "Yesterday user type",
        "type",
        "mdi:home-account",
        None,
        None,
    ],
    "yesterday_usage": [
        "Yesterday usage",
        ENERGY_KILO_WATT_HOUR,
        "mdi:flash",
        SensorStateClass.TOTAL,
        SensorDeviceClass.ENERGY,
    ],
    "yesterday_consumption": [
        "Yesterday consumption",
        ENERGY_KILO_WATT_HOUR,
        "mdi:flash",
        SensorStateClass.TOTAL,
        SensorDeviceClass.ENERGY,
    ],
    "yesterday_consumption_peak": [
        "Yesterday consumption peak",
        ENERGY_KILO_WATT_HOUR,
        "mdi:flash",
        None,
        SensorDeviceClass.ENERGY,
    ],
    "yesterday_consumption_offpeak": [
        "Yesterday consumption offpeak",
        ENERGY_KILO_WATT_HOUR,
        "mdi:flash",
        None,
        SensorDeviceClass.ENERGY,
    ],
    "yesterday_consumption_shoulder": [
        "Yesterday consumption shoulder",
        ENERGY_KILO_WATT_HOUR,
        "mdi:flash",
        None,
        SensorDeviceClass.ENERGY,
    ],
    "yesterday_consumption_controlled_load": [
        "Yesterday consumption controlled load",
        ENERGY_KILO_WATT_HOUR,
        "mdi:flash",
        None,
        SensorDeviceClass.ENERGY,
    ],
    "yesterday_generation": [
        "Yesterday generation",
        ENERGY_KILO_WATT_HOUR,
        "mdi:flash",
        None,
        SensorDeviceClass.ENERGY,
    ],
    "yesterday_cost_total": [
        "Yesterday cost total",
        CURRENCY_DOLLAR,
        "mdi:currency-usd",
        None,
        None,
    ],
    "yesterday_cost_consumption": [
        "Yesterday cost consumption",
        ENERGY_KILO_WATT_HOUR,
        "mdi:currency-usd",
        None,
        None,
    ],
    "yesterday_cost_generation": [
        "Yesterday cost generation",
        CURRENCY_DOLLAR,
        "mdi:currency-usd",
        None,
        None,
    ],
    "yesterday_cost_difference": [
        "Yesterday cost difference",
        CURRENCY_DOLLAR,
        "mdi:currency-usd",
        None,
        None,
    ],
    "yesterday_percentage_difference": [
        "Yesterday percentage difference",
        PERCENTAGE,
        "mdi:percent",
        None,
        None,
    ],
    "yesterday_difference_message": [
        "Yesterday difference message",
        "text",
        "mdi:clipboard-text",
        None,
        None,
    ],
    "yesterday_consumption_difference": [
        "Yesterday consumption difference",
        ENERGY_KILO_WATT_HOUR,
        "mdi:flash",
        None,
        SensorDeviceClass.ENERGY,
    ],
    "yesterday_consumption_change": [
        "Yesterday consumption change",
        ENERGY_KILO_WATT_HOUR,
        "mdi:swap-vertical",
        None,
        SensorDeviceClass.ENERGY,
    ],
    "yesterday_suburb_average": [
        "Yesterday suburb average",
        ENERGY_KILO_WATT_HOUR,
        "mdi:flash",
        None,
        SensorDeviceClass.ENERGY,
    ],
    "previous_day_usage": [
        "Previous day usage",
        ENERGY_KILO_WATT_HOUR,
        "mdi:flash",
        None,
        SensorDeviceClass.ENERGY,
    ],
    "previous_day_consumption": [
        "Previous day consumption",
        ENERGY_KILO_WATT_HOUR,
        "mdi:flash",
        None,
        SensorDeviceClass.ENERGY,
    ],
    "previous_day_generation": [
        "Previous day generation",
        ENERGY_KILO_WATT_HOUR,
        "mdi:flash",
        None,
        SensorDeviceClass.ENERGY,
    ],
    "supply_charge": ["Supply charge", CURRENCY_DOLLAR, "mdi:currency-usd", None, None],
    "weekday_peak_cost": [
        "Weekday peak cost",
        CURRENCY_DOLLAR,
        "mdi:currency-usd",
        None,
        None,
    ],
    "weekday_offpeak_cost": [
        "Weekday offpeak cost",
        CURRENCY_DOLLAR,
        "mdi:currency-usd",
        None,
        None,
    ],
    "weekday_shoulder_cost": [
        "Weekday shoulder cost",
        CURRENCY_DOLLAR,
        "mdi:currency-usd",
        None,
        None,
    ],
    "controlled_load_cost": [
        "Controlled load cost",
        CURRENCY_DOLLAR,
        "mdi:currency-usd",
        None,
        None,
    ],
    "weekend_offpeak_cost": [
        "Weekend offpeak cost",
        CURRENCY_DOLLAR,
        "mdi:currency-usd",
        None,
        None,
    ],
    "single_rate_cost": [
        "Single rate cost",
        CURRENCY_DOLLAR,
        "mdi:currency-usd",
        None,
        None,
    ],
    "generation_cost": [
        "Generation cost",
        CURRENCY_DOLLAR,
        "mdi:currency-usd",
        None,
        None,
    ],
    "this_week_user_type": [
        "This week user type",
        "type",
        "mdi:home-account",
        None,
        None,
    ],
    "this_week_usage": [
        "This week usage",
        ENERGY_KILO_WATT_HOUR,
        "mdi:flash",
        SensorStateClass.TOTAL,
        SensorDeviceClass.ENERGY,
    ],
    "this_week_consumption": [
        "This week consumption",
        ENERGY_KILO_WATT_HOUR,
        "mdi:flash",
        SensorStateClass.TOTAL,
        SensorDeviceClass.ENERGY,
    ],
    "this_week_consumption_peak": [
        "This week consumption peak",
        ENERGY_KILO_WATT_HOUR,
        "mdi:flash",
        None,
        SensorDeviceClass.ENERGY,
    ],
    "this_week_consumption_offpeak": [
        "This week consumption offpeak",
        ENERGY_KILO_WATT_HOUR,
        "mdi:flash",
        None,
        SensorDeviceClass.ENERGY,
    ],
    "this_week_consumption_shoulder": [
        "This week consumption shoulder",
        ENERGY_KILO_WATT_HOUR,
        "mdi:flash",
        None,
        SensorDeviceClass.ENERGY,
    ],
    "this_week_consumption_controlled_load": [
        "This week consumption controlled load",
        ENERGY_KILO_WATT_HOUR,
        "mdi:flash",
        None,
        SensorDeviceClass.ENERGY,
    ],
    "this_week_generation": [
        "This week generation",
        ENERGY_KILO_WATT_HOUR,
        "mdi:flash",
        SensorStateClass.TOTAL,
        SensorDeviceClass.ENERGY,
    ],
    "this_week_cost_total": [
        "This week cost total",
        CURRENCY_DOLLAR,
        "mdi:currency-usd",
        SensorStateClass.TOTAL,
        None,
    ],
    "this_week_cost_consumption": [
        "This week cost consumption",
        CURRENCY_DOLLAR,
        "mdi:currency-usd",
        SensorStateClass.TOTAL,
        None,
    ],
    "this_week_cost_generation": [
        "This week cost generation",
        CURRENCY_DOLLAR,
        "mdi:currency-usd",
        None,
        None,
    ],
    "this_week_cost_difference": [
        "This week cost difference",
        CURRENCY_DOLLAR,
        "mdi:currency-usd",
        None,
        None,
    ],
    "this_week_percentage_difference": [
        "This week percentage difference",
        PERCENTAGE,
        "mdi:percent",
        None,
        None,
    ],
    "this_week_difference_message": [
        "This week difference message",
        "text",
        "mdi:clipboard-text",
        None,
        None,
    ],
    "this_week_consumption_difference": [
        "This week consumption difference",
        ENERGY_KILO_WATT_HOUR,
        "mdi:flash",
        None,
        SensorDeviceClass.ENERGY,
    ],
    "this_week_consumption_change": [
        "This week consumption change",
        ENERGY_KILO_WATT_HOUR,
        "mdi:swap-vertical",
        None,
        SensorDeviceClass.ENERGY,
    ],
    "this_week_suburb_average": [
        "This week suburb average",
        ENERGY_KILO_WATT_HOUR,
        "mdi:flash",
        SensorStateClass.MEASUREMENT,
        SensorDeviceClass.ENERGY,
    ],
    "last_week_usage": [
        "Last week usage",
        ENERGY_KILO_WATT_HOUR,
        "mdi:flash",
        SensorStateClass.TOTAL,
        SensorDeviceClass.ENERGY,
    ],
    "last_week_consumption": [
        "Last week consumption",
        ENERGY_KILO_WATT_HOUR,
        "mdi:flash",
        SensorStateClass.TOTAL,
        SensorDeviceClass.ENERGY,
    ],
    "last_week_generation": [
        "Last week generation",
        ENERGY_KILO_WATT_HOUR,
        "mdi:flash",
        SensorStateClass.TOTAL,
        SensorDeviceClass.ENERGY,
    ],
    "this_month_user_type": [
        "This month user type",
        "type",
        "mdi:home-account",
        None,
        None,
    ],
    "this_month_usage": [
        "This month usage",
        ENERGY_KILO_WATT_HOUR,
        "mdi:flash",
        SensorStateClass.TOTAL,
        SensorDeviceClass.ENERGY,
    ],
    "this_month_consumption": [
        "This month consumption",
        ENERGY_KILO_WATT_HOUR,
        "mdi:flash",
        SensorStateClass.TOTAL,
        SensorDeviceClass.ENERGY,
    ],
    "this_month_consumption_peak": [
        "This month consumption peak",
        ENERGY_KILO_WATT_HOUR,
        "mdi:flash",
        SensorStateClass.TOTAL,
        SensorDeviceClass.ENERGY,
    ],
    "this_month_consumption_offpeak": [
        "This month consumption offpeak",
        ENERGY_KILO_WATT_HOUR,
        "mdi:flash",
        None,
        SensorDeviceClass.ENERGY,
    ],
    "this_month_consumption_shoulder": [
        "This month consumption shoulder",
        ENERGY_KILO_WATT_HOUR,
        "mdi:flash",
        None,
    ],
    "this_month_consumption_controlled_load": [
        "This month consumption controlled load",
        ENERGY_KILO_WATT_HOUR,
        "mdi:flash",
        None,
        SensorDeviceClass.ENERGY,
    ],
    "this_month_generation": [
        "This month generation",
        ENERGY_KILO_WATT_HOUR,
        "mdi:flash",
        SensorStateClass.TOTAL,
        SensorDeviceClass.ENERGY,
    ],
    "this_month_cost_total": [
        "This month cost total",
        ENERGY_KILO_WATT_HOUR,
        "mdi:currency-usd",
        SensorStateClass.TOTAL,
        None,
    ],
    "this_month_cost_consumption": [
        "This month cost consumption",
        ENERGY_KILO_WATT_HOUR,
        "mdi:currency-usd",
        SensorStateClass.TOTAL,
        None,
    ],
    "this_month_cost_generation": [
        "This month cost generation",
        ENERGY_KILO_WATT_HOUR,
        "mdi:currency-usd",
        SensorStateClass.TOTAL,
        None,
    ],
    "this_month_cost_difference": [
        "This month cost difference",
        ENERGY_KILO_WATT_HOUR,
        "mdi:currency-usd",
        None,
        None,
    ],
    "this_month_percentage_difference": [
        "This month percentage difference",
        PERCENTAGE,
        "mdi:percent",
        None,
        None,
    ],
    "this_month_difference_message": [
        "This month difference message",
        "text",
        "mdi:clipboard-text",
        None,
        None,
    ],
    "this_month_consumption_difference": [
        "This month consumption difference",
        ENERGY_KILO_WATT_HOUR,
        "mdi:flash",
        None,
        SensorDeviceClass.ENERGY,
    ],
    "this_month_consumption_change": [
        "This month consumption change",
        ENERGY_KILO_WATT_HOUR,
        "mdi:swap-vertical",
        None,
        SensorDeviceClass.ENERGY,
    ],
    "this_month_suburb_average": [
        "This month suburb average",
        ENERGY_KILO_WATT_HOUR,
        "mdi:flash",
        SensorStateClass.MEASUREMENT,
        SensorDeviceClass.ENERGY,
    ],
    "last_month_usage": [
        "Last month usage",
        ENERGY_KILO_WATT_HOUR,
        "mdi:flash",
        SensorStateClass.TOTAL,
        SensorDeviceClass.ENERGY,
    ],
    "last_month_consumption": [
        "Last month consumption",
        ENERGY_KILO_WATT_HOUR,
        "mdi:flash",
        SensorStateClass.TOTAL,
        SensorDeviceClass.ENERGY,
    ],
    "last_month_generation": [
        "Last month generation",
        ENERGY_KILO_WATT_HOUR,
        "mdi:flash",
        SensorStateClass.TOTAL,
        SensorDeviceClass.ENERGY,
    ],
}

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend(
    {
        vol.Required(CONF_MONITORED_VARIABLES): vol.All(
            cv.ensure_list, [vol.In(SENSOR_TYPES)]
        ),
        vol.Required(CONF_USERNAME): cv.string,
        vol.Required(CONF_PASSWORD): cv.string,
        vol.Optional(CONF_NAME, default=DEFAULT_NAME): cv.string,
    }
)


def setup_platform(hass, config, add_devices, discovery_info=None):
    """Set up the Jemena Outlook sensor."""
    # Create a data fetcher to support all of the configured sensors. Then make
    # the first call to init the data.

    username = config.get(CONF_USERNAME)
    password = config.get(CONF_PASSWORD)

    try:
        jemenaoutlook_data = JemenaOutlookData(username, password)
        jemenaoutlook_data.get_data()

    except requests.exceptions.HTTPError as error:
        _LOGGER.error("Failt login: %s", error)
        return False

    name = config.get(CONF_NAME)

    sensors = []
    for variable in config[CONF_MONITORED_VARIABLES]:
        sensors.append(JemenaOutlookSensor(jemenaoutlook_data, variable, name))

    add_devices(sensors)


class JemenaOutlookSensor(Entity):
    """Implementation of a Jemena Outlook sensor."""

    def __init__(self, jemenaoutlook_data, sensor_type, name):
        """Initialize the sensor."""

        self.client_name = name
        self.type = sensor_type
        self._name = SENSOR_TYPES[sensor_type][0]
        self._unit_of_measurement = SENSOR_TYPES[sensor_type][1]
        self._icon = SENSOR_TYPES[sensor_type][2]
        self._state_class = SENSOR_TYPES[sensor_type][3]
        self._device_class = SENSOR_TYPES[sensor_type][4]
        self.jemenaoutlook_data = jemenaoutlook_data
        self._state = None

        _LOGGER.info("init data: %s", jemenaoutlook_data.data)

        if (
            self.type is not None
            and self.jemenaoutlook_data.data.get(self.type) is not None
        ):
            if type(self.jemenaoutlook_data.data[self.type]) == type(""):
                self._state = self.jemenaoutlook_data.data[self.type]
            else:
                self._state = round(self.jemenaoutlook_data.data[self.type], 2)

    @property
    def name(self):
        """Return the name of the sensor."""
        return "{} {}".format(self.client_name, self._name)

    @property
    def state(self):
        """Return the state of the sensor."""
        return self._state

    @property
    def state_class(self):
        """
        Return the state_class of the sensor for energy stats
        """
        return self._state_class

    @property
    def device_class(self):
        """
        Return the device_class of the sensor for energy stats
        """
        return self._device_class

    @property
    def unit_of_measurement(self):
        """Return the unit of measurement of this entity, if any."""
        return self._unit_of_measurement

    @property
    def icon(self):
        """Icon to use in the frontend, if any."""
        return self._icon

    def update(self):
        """Get the latest data from Jemena Outlook and update the state."""
        self.jemenaoutlook_data.update()

        if self.type in self.jemenaoutlook_data.data is not None:
            if type(self.jemenaoutlook_data.data[self.type]) == type(""):
                self._state = self.jemenaoutlook_data.data[self.type]
            else:
                self._state = round(self.jemenaoutlook_data.data[self.type], 2)


class JemenaOutlookData(object):
    """Get data from JemenaOutlook."""

    def __init__(self, username, password):
        """Initialize the data object."""
        self.client = JemenaOutlookClient(username, password, REQUESTS_TIMEOUT)
        self.data = {}

    def _fetch_data(self):
        """Fetch latest data from Jemena Outlook."""
        try:
            self.client.fetch_data()
        except JemenaOutlookError as exp:
            _LOGGER.error("Error on receive last Jemena Outlook data: %s", exp)
            return

    def get_data(self):
        """Return the contract list."""
        # Fetch data
        self._fetch_data()
        self.data = self.client.get_data()
        return self.data

    @Throttle(MIN_TIME_BETWEEN_UPDATES)
    def update(self):
        """Return the latest collected data from Jemena Outlook."""
        self._fetch_data()
        self.data = self.client.get_data()


class JemenaOutlookError(Exception):
    pass


class JemenaOutlookClient(object):
    def __init__(self, username, password, timeout=REQUESTS_TIMEOUT):
        """Initialize the client object."""
        self.username = username
        self.password = password
        self._data = {}
        self._timeout = timeout
        self._session = None

    def _get_login_page(self):
        """Go to the login page."""
        try:
            raw_res = self._session.get(HOME_URL, timeout=REQUESTS_TIMEOUT)

        except OSError:
            raise JemenaOutlookError("Can not connect to login page")

        # Get login url
        soup = BeautifulSoup(raw_res.content, "html.parser")

        form_node = soup.find("form", {"id": "loginForm"})
        if form_node is None:
            raise JemenaOutlookError("No login form found")

        login_url = form_node.attrs.get("action")
        if login_url is None:
            raise JemenaOutlookError("Cannot find login url")

        return login_url

    def _post_login_page(self, login_url):
        """Login to Jemena Electricity Outlook website."""
        form_data = {
            "login_email": self.username,
            "login_password": self.password,
            "submit": "Sign In",
        }
        try:
            raw_res = self._session.post(
                "{}/login_security_check".format(HOST),
                data=form_data,
                timeout=REQUESTS_TIMEOUT,
            )

        except OSError as e:
            raise JemenaOutlookError("Cannot submit login form {0}".format(e.errno))

        if raw_res.status_code != 200:
            raise JemenaOutlookError(
                "Login error: Bad HTTP status code. {}".format(raw_res.status_code)
            )

        return True

    def _get_tariffs(self):
        """Get tariff data. This data must be setup by the user first and is not automatically available."""

        try:
            url = "{}/electricityView/index".format(HOST)
            raw_res = self._session.get(url, timeout=REQUESTS_TIMEOUT)

        except OSError:
            raise JemenaOutlookError("Can not connect to login page")

        # Get login url
        soup = BeautifulSoup(raw_res.content, "html.parser")
        tariff_script = soup.find("script", text=re.compile("var tariff = "))

        if tariff_script is not None:

            json_text = re.search(
                r"^\s*var tariff =\s*({.*?})\s*;\s*$",
                tariff_script.string,
                flags=re.DOTALL | re.MULTILINE,
            ).group(1)
            data = json.loads(json_text)

            tariff_data = {
                "supply_charge": self._strip_currency(data["supplyCharge"]),
                "weekday_peak_cost": self._strip_currency(data["weekdayPeakCost"]),
                "weekday_offpeak_cost": self._strip_currency(
                    data["weekdayOffpeakCost"]
                ),
                "weekday_shoulder_cost": self._strip_currency(
                    data["weekdayShoulderCost"]
                ),
                "controlled_load_cost": self._strip_currency(
                    data["controlledLoadCost"]
                ),
                "weekend_offpeak_cost": self._strip_currency(
                    data["weekendOffpeakCost"]
                ),
                "single_rate_cost": self._strip_currency(data["singleRateCost"]),
                "generation_cost": self._strip_currency(data["generationCost"]),
            }

        return tariff_data

    def _get_daily_data(self, days_ago):
        """Get daily data."""

        try:
            #'{}/electricityView/period/day/1'.format(HOST)
            url = "{}/{}/{}".format(PERIOD_URL, "day", days_ago)
            raw_res = self._session.get(url, timeout=REQUESTS_TIMEOUT)
        except OSError as e:
            _LOGGER.debug("exception data {}".format(e.errstring))
            raise JemenaOutlookError("Cannot get daily data")
        try:
            json_output = raw_res.json()
        except (OSError, json.decoder.JSONDecodeError):
            raise JemenaOutlookError("Could not get daily data: {}".format(raw_res))

        if not json_output.get("selectedPeriod"):
            raise JemenaOutlookError("Could not get daily data for selectedPeriod")

        _LOGGER.debug("Jemena outlook daily data: %s", json_output)

        daily_data = self._extract_period_data(json_output, "yesterday", "previous_day")

        return daily_data

    def _get_weekly_data(self, weeks_ago):
        """Get weekly data."""

        try:
            # PERIOD_URL
            url = "{}/{}/{}".format(PERIOD_URL, "week", weeks_ago)
            raw_res = self._session.get(url, timeout=REQUESTS_TIMEOUT)

        except OSError as e:
            _LOGGER.debug("exception data {}".format(e.errstring))
            raise JemenaOutlookError("Cannot get daily data")
        try:
            json_output = raw_res.json()

        except (OSError, json.decoder.JSONDecodeError):
            raise JemenaOutlookError("Could not get daily data: {}".format(raw_res))

        if not json_output.get("selectedPeriod"):
            raise JemenaOutlookError("Could not get daily data for selectedPeriod")

        _LOGGER.debug("Jemena outlook weekly data: %s", json_output)

        weekly_data = self._extract_period_data(json_output, "this_week", "last_week")

        return weekly_data

    def _get_monthly_data(self, months_ago):
        """Get weekly data."""

        try:
            # PERIOD_URL
            url = "{}/{}/{}".format(PERIOD_URL, "month", months_ago)
            raw_res = self._session.get(url, timeout=REQUESTS_TIMEOUT)

        except OSError as e:
            _LOGGER.debug("exception data {}".format(e.errstring))
            raise JemenaOutlookError("Cannot get daily data")
        try:
            json_output = raw_res.json()

        except (OSError, json.decoder.JSONDecodeError):
            raise JemenaOutlookError("Could not get daily data: {}".format(raw_res))

        if not json_output.get("selectedPeriod"):
            raise JemenaOutlookError("Could not get daily data for selectedPeriod")

        _LOGGER.debug("Jemena outlook monthly data: %s", json_output)

        monthly_data = self._extract_period_data(
            json_output, "this_month", "last_month"
        )

        return monthly_data

    def _extract_period_data(self, json_data, current, previous):

        costDifference = json_data.get("costDifference")
        costDifferenceMessage = json_data.get("costDifferenceMessage")
        kwhPercentageDifference = json_data.get("kwhPercentageDifference")

        consumptionDifference = json_data.get("consumptionDifferenceMessage")

        selectedPeriod = json_data.get("selectedPeriod")

        netConsumption = selectedPeriod["netConsumption"]
        averageNetConsumptionPerSubPeriod = selectedPeriod[
            "averageNetConsumptionPerSubPeriod"
        ]
        peakConsumption = self._sum_period_array(
            selectedPeriod["consumptionData"]["peak"], 3
        )
        offPeakConsumption = self._sum_period_array(
            selectedPeriod["consumptionData"]["offpeak"], 3
        )
        shoulderConsumption = self._sum_period_array(
            selectedPeriod["consumptionData"]["shoulder"], 3
        )
        controlledLoadConsumption = self._sum_period_array(
            selectedPeriod["consumptionData"]["controlledLoad"], 3
        )
        generation = self._sum_period_array(
            selectedPeriod["consumptionData"]["generation"], 3
        )
        suburbAverage = self._sum_period_array(
            selectedPeriod["consumptionData"]["suburbAverage"], 3
        )

        costDataPeak = self._sum_period_array(selectedPeriod["costData"]["peak"], 2)
        costDataOffPeak = self._sum_period_array(
            selectedPeriod["costData"]["offpeak"], 2
        )
        costDataShoulder = self._sum_period_array(
            selectedPeriod["costData"]["shoulder"], 2
        )
        costDataControlledLoad = self._sum_period_array(
            selectedPeriod["costData"]["controlledLoad"], 2
        )
        costDataGeneration = self._sum_period_array(
            selectedPeriod["costData"]["generation"], 2
        )

        previousPeriod = json_data.get("comparisonPeriod")

        previousPeriodNetConsumption = previousPeriod["netConsumption"]
        previousPeriodPeakConsumption = self._sum_period_array(
            previousPeriod["consumptionData"]["peak"], 3
        )
        previousPeriodOffPeakConsumption = self._sum_period_array(
            previousPeriod["consumptionData"]["offpeak"], 3
        )
        previousPeriodShoulderConsumption = self._sum_period_array(
            previousPeriod["consumptionData"]["shoulder"], 3
        )
        previousPeriodControlledLoadConsumption = self._sum_period_array(
            previousPeriod["consumptionData"]["controlledLoad"], 3
        )
        previousPeriodGeneration = self._sum_period_array(
            previousPeriod["consumptionData"]["generation"], 3
        )
        previousPeriodSuburbAverage = self._sum_period_array(
            previousPeriod["consumptionData"]["suburbAverage"], 3
        )

        period_data = {
            current + "_user_type": "consumer" if netConsumption > 0 else "generator",
            current + "_usage": netConsumption,
            current
            + "_average_net_usage_per_sub_period": averageNetConsumptionPerSubPeriod,
            current
            + "_consumption": round(
                peakConsumption
                + offPeakConsumption
                + shoulderConsumption
                + controlledLoadConsumption,
                3,
            ),
            current + "_consumption_peak": peakConsumption,
            current + "_consumption_offpeak": offPeakConsumption,
            current + "_consumption_shoulder": shoulderConsumption,
            current + "_consumption_controlled_load": controlledLoadConsumption,
            current + "_generation": generation,
            current
            + "_cost_total": round(
                costDataPeak
                + costDataOffPeak
                + costDataShoulder
                + costDataControlledLoad
                + costDataGeneration,
                2,
            ),
            current
            + "_cost_consumption": round(
                costDataPeak
                + costDataOffPeak
                + costDataShoulder
                + costDataControlledLoad,
                2,
            ),
            current + "_cost_generation": abs(costDataGeneration),
            current + "_suburb_average": suburbAverage,
            current + "_cost_difference": costDifference,
            current + "_difference_message": costDifferenceMessage["text"],
            current + "_percentage_difference": kwhPercentageDifference,
            current
            + "_consumption_difference": round(
                netConsumption - previousPeriodNetConsumption, 3
            ),
            current + "_consumption_change": costDifferenceMessage["change"],
            previous
            + "_usage": round(
                previousPeriodPeakConsumption
                + previousPeriodOffPeakConsumption
                + previousPeriodShoulderConsumption
                + previousPeriodControlledLoadConsumption
                - previousPeriodGeneration,
                3,
            ),
            previous
            + "_consumption": round(
                previousPeriodPeakConsumption
                + previousPeriodOffPeakConsumption
                + previousPeriodShoulderConsumption
                + previousPeriodControlledLoadConsumption,
                3,
            ),
            previous + "_generation": previousPeriodGeneration,
        }
        return period_data

    def _sum_period_array(self, json_array_of_value, rounding_digits):
        total_value = 0.0
        for value in json_array_of_value:
            if value is not None:
                total_value += value
        return round(total_value, rounding_digits)

    def _strip_currency(self, amount):

        return locale.atof(amount.strip("$"))

    def fetch_data(self):
        """Get the latest data from Jemena Outlook."""

        # setup requests session
        self._session = requests.Session()

        # Get login page
        login_url = self._get_login_page()

        # Post login page
        self._post_login_page(login_url)

        self._data.update(self._get_tariffs())

        # Get Daily Usage data
        self._data.update(self._get_daily_data(1))

        # Get Daily Usage data
        self._data.update(self._get_weekly_data(0))

        # Get Daily Usage data
        self._data.update(self._get_monthly_data(0))

    def get_data(self):
        return self._data
