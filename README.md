## pymosyle

Simple Python Abstraction Layer for the Mosyle Manager (Schools) and Mosyle Business APIs.

# Supported functions
- List Devices
- Get Device Information
- Update Device Information

# Example
```
from pymosyle import MosyleAPI

# for mosyle business
api = MosyleAPI("API TOKEN", "EMAIL", "PASSWORD", None, "business")
# for mosyle manager
api = MosyleAPI("API TOKEN", "EMAIL", "PASSWORD", None, "school")

print(api.get_devices("macos"))

api.update_device("macos", "SERIAL", {"asset_tag": "1234"})
```
