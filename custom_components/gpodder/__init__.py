"""
Component to integrate with gPodder.

For more details about this component, please refer to
https://github.com/custom-components/gpodder
"""
import os
from datetime import timedelta
import logging
import voluptuous as vol
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers import discovery
from homeassistant.util import Throttle
from .const import (
    DOMAIN_DATA,
    DOMAIN,
    ISSUE_URL,
    PLATFORMS,
    REQUIRED_FILES,
    STARTUP,
    URL,
    VERSION,
    CONF_SENSOR,
    CONF_ENABLED,
    CONF_NAME,
    CONF_USERNAME,
    CONF_PASSWORD,
    CONF_DEVICE,
    DEAFULT_NAME,
    REQUIREMENTS
)

MIN_TIME_BETWEEN_UPDATES = timedelta(minutes=30)

_LOGGER = logging.getLogger(__name__)

SENSOR_SCHEMA = vol.Schema(
    {
        vol.Optional(CONF_ENABLED, default=True): cv.boolean,
        vol.Optional(CONF_NAME, default=DEAFULT_NAME): cv.string,
        vol.Optional(CONF_DEVICE, default="homeassistant"): cv.string,
    }
)

CONFIG_SCHEMA = vol.Schema(
    {
        DOMAIN: vol.Schema(
            {
                vol.Required(CONF_USERNAME): cv.string,
                vol.Required(CONF_PASSWORD): cv.string,
                vol.Optional(CONF_SENSOR, default=[{}]): vol.All(cv.ensure_list, [SENSOR_SCHEMA]),
            }
        )
    },
    extra=vol.ALLOW_EXTRA,
)


async def async_setup(hass, config):
    """Set up this component."""
    from mygpoclient import api
    # Print startup message
    startup = STARTUP.format(name=DOMAIN, version=VERSION, issueurl=ISSUE_URL)
    _LOGGER.info(startup)

    # Check that all required files are present
    file_check = await check_files(hass)
    if not file_check:
        return False

    # Create DATA dict
    hass.data[DOMAIN_DATA] = {}
    hass.data[DOMAIN] = {}
    component_config = config[DOMAIN]

    # Create gPodder client
    hass.data[DOMAIN]["client"] = api.MygPodderClient(component_config[CONF_USERNAME], component_config[CONF_PASSWORD])

    # Load platforms
    for platform in PLATFORMS:
        # Get platform specific configuration
        platform_config = component_config.get(platform, {})

        if not platform_config:
            continue

        for entry in platform_config:
            entry_config = entry

            # If entry is not enabled, skip.
            if not entry_config[CONF_ENABLED]:
                continue

            hass.async_create_task(
                discovery.async_load_platform(
                    hass, platform, DOMAIN, entry_config, config
                )
            )
    return True


@Throttle(MIN_TIME_BETWEEN_UPDATES)
async def update_data(hass, device):
    """Update data."""
    import feedparser

    try:
        urls = hass.data[DOMAIN]["client"].get_subscriptions(device)
        hass.data[DOMAIN_DATA] = urls

        for url in urls:
            parsed_podcast = feedparser.parse(url)

            if not parsed_podcast:
                continue

            feed = parsed_podcast.feed

            podcast = {
                "url": url,
                "title": feed.get("title", ""),
                "summary": feed.get("summary", ""),
                "image": feed.get("image", {}).get("href", "")
            }

            _LOGGER.info(podcast)

            parsed_episodes = []

            for i, entry in enumerate(parsed_podcast.get("entries", [])):
                if i > 5:
                    break
                parsed_episodes.append(parse_entry(entry))

            # _LOGGER.info(parsed_episodes)
    except Exception as error:  # pylint: disable=broad-except
        _LOGGER.error("Could not update data - %s", error)


def parse_entry(entry):
    episode = {
        "title": entry.get("title", ""),
        "summary": entry.content[0].value,
        "url": entry.get("media_content", {}),
        "published": entry.get("published", 0),
    }

    _LOGGER.info(episode)
    return episode


async def check_files(hass):
    """Return bool that indicates if all files are present."""
    # Verify that the user downloaded all files.
    base = "{}/custom_components/{}/".format(hass.config.path(), DOMAIN)
    missing = []
    for file in REQUIRED_FILES:
        fullpath = "{}{}".format(base, file)
        if not os.path.exists(fullpath):
            missing.append(file)

    if missing:
        _LOGGER.critical("The following files are missing: %s", str(missing))
        returnvalue = False
    else:
        returnvalue = True

    return returnvalue
