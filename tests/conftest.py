"""Import the API adapter without requiring the full Home Assistant runtime."""

import sys
from pathlib import Path
from types import ModuleType

root = Path(__file__).resolve().parents[1]
package = ModuleType("custom_components")
package.__path__ = [str(root / "custom_components")]
sys.modules["custom_components"] = package

incus = ModuleType("custom_components.incus")
incus.__path__ = [str(root / "custom_components" / "incus")]
sys.modules["custom_components.incus"] = incus
