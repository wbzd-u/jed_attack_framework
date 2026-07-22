# Kaggle integration

The runtime should be bundled into `/kaggle/working` before the official
inference server starts. A notebook cell can use:

```python
from pathlib import Path
import sys

source = Path("/kaggle/input/<your-framework-dataset>/jed_attack_framework")
sys.path.insert(0, str(source.parent))

from jed_attack_framework.bundle_submission import bundle
bundle(source, "/kaggle/working")
```

The generated `/kaggle/working/attack.py` imports only the standard library,
the bundled `jedfw` package, and the competition SDK. PyRIT, Inspect AI,
Promptfoo, garak, and other research packages remain offline dependencies and
must not be imported by the hosted submission unless the image explicitly
contains them.

The official server cell remains responsible for starting the gateway. The
algorithm entry point only implements `AttackAlgorithm.run`.
