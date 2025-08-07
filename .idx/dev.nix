# To learn more about how to use Nix to configure your environment
# see: https://developers.google.com/idx/guides/customize-idx-env
{ pkgs, ... }: {
  # Which nixpkgs channel to use.
  channel = "stable-24.05"; # or "unstable"
  # Use https://search.nixos.org/packages to find packages
  packages = [
    # python311Full is required for venv support
    pkgs.python311Full
  ];
  # Sets environment variables in the workspace
  env = {
    # This ensures that tools use the Python from your virtual environment
    PATH = "$PWD/.venv/bin:$PATH";
    # Helps the VS Code Python extension find your virtual environment
    VIRTUAL_ENV = "$PWD/.venv";
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
      # Runs when a workspace is first created
      onCreate = {
        # Create a virtual environment named .venv
        create-venv = "python -m venv .venv";
        # Install dependencies from requirements.txt into the virtual environment.
        # The PATH environment variable ensures we use the correct pip.
        pip-install = "pip install -r requirements.txt";
      };
      # Runs when the workspace is (re)started
      onStart = {
        # The PATH environment variable ensures we use the correct python interpreter.
        start-bot = "python bot.py";
      };
    };
  };
}
