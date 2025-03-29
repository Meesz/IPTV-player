"""
This module contains the BaseController class, which serves as a base class for all controllers
in the application.
"""

import logging

logger = logging.getLogger(__name__)


class BaseController:
    """Base class for all controllers in the application.

    The BaseController provides common functionality and a consistent interface
    for all controllers in the application.
    """

    def __init__(self, config=None):
        """Initialize the BaseController with optional configuration.

        Args:
            config: Optional configuration dictionary or object
        """
        self.config = config or {}
        logger.debug(f"BaseController initialized with config: {self.config}")

    def update_config(self, new_config):
        """Update the controller's configuration.

        Args:
            new_config: New configuration to merge with existing config
        """
        if not new_config:
            return

        if isinstance(new_config, dict) and isinstance(self.config, dict):
            self.config.update(new_config)
        else:
            self.config = new_config

        logger.debug(f"BaseController config updated: {self.config}")

    def get_config_value(self, key, default=None):
        """Get a configuration value by key.

        Args:
            key: The configuration key to look up
            default: The default value to return if the key is not found

        Returns:
            The configuration value or the default
        """
        if isinstance(self.config, dict):
            return self.config.get(key, default)
        return default

    def reset(self):
        """Reset the controller to its initial state.

        This method should be overridden by subclasses to provide
        controller-specific reset functionality.
        """
        logger.debug("BaseController reset") 