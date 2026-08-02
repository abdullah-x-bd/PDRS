from __future__ import annotations

"""Run the comparison with CombOL's reserved neutral atom handled explicitly.

CombOL treats `dummy` as an implicit neutral symbol and therefore does not
include it in `Context.variable_key_map`. The shared comparison specification
uses that symbol only to pad alternatives to equal combinatorial size. This
runner removes reserved symbols from the explicit parameter dictionary and
sets every real atom weight to one. Consequently every complete finite object
has the same product weight, including alternatives padded with neutral atoms.
"""

from combol.context import Context

_original_translate = Context._translate_str_params


def _translate_unit_weights(self: Context, params: dict[str, float]):
    normalized = {
        key: 1.0
        for key in params
        if key in self.variable_key_map
    }
    return _original_translate(self, normalized)


Context._translate_str_params = _translate_unit_weights

from run_comparison import run


if __name__ == "__main__":
    run()
