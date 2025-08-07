# This is a Nix configuration file.
# It is used by Firebase Studio to set up the development environment.
# It is based on the Nix package manager.
#
# You can find more information about Nix here:
# https://nixos.org/
{ pkgs, ... }: {
  # The channel determines which version of the Nix package collection is used.
  # "stable-24.05" is the latest stable channel.
  # "unstable" is the latest unstable channel.
  channel = "stable-24.05"; # or "unstable"

  # A list of packages to install from the specified channel.
  # You can search for packages on https://search.nixos.org/packages
  packages = [
    # Create a Python environment with aiogram
    (pkgs.python3.withPackages (ps: [
      ps.aiogram
      # You can add other python packages here, e.g. ps.requests
    ]))
  ];

  # A set of environment variables to define within the workspace.
  env = {
    # IMPORTANT: Replace this with your actual Telegram token
    TELEGRAM_API_TOKEN = "YOUR_TELEGRAM_API_TOKEN_HERE";
  };
  idx = {
    # Search for the extensions you want on https://open-vsx.org/ and use "publisher.id"
    extensions = [
      "ms-python.python"
    ];
    # A web preview is not needed for this bot
    previews = {
      enable = false;
    };
    # Workspace lifecycle hooks
    workspace = {
      # onStart runs every time the workspace is (re)started
      onStart = {
        # Start the bot
        start-bot = "python bot.py";
      };
    };
  };
}
