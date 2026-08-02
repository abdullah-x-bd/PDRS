# Finance adapters

Adapters are optional and imported lazily.

## QuantLib

Install:

```bash
pip install "finspace[quantlib]"
```

```python
from finspace.adapters import QuantLibEuropeanOptionPricer
from finspace.templates import european_option_space

space = european_option_space()
pricer = QuantLibEuropeanOptionPricer()
result = pricer(space.unrank(100))
```

The adapter supports analytic, CRR binomial, and finite-difference European option engines.

## SimpleFIX

Install:

```bash
pip install "finspace[fix]"
```

```python
from finspace.adapters import SimpleFixNewOrderSingleEncoder
```

The adapter emits encoded FIX 4.4 New Order Single messages. Session-level validation, transport, sequence-number management, and exchange-specific profiles remain the application's responsibility.

## ISO 20022

Install:

```bash
pip install "finspace[iso20022]"
```

```python
from finspace.adapters import ISO20022PaymentBuilder
```

The included builder provides compact bounded pain.001 and pacs.008 examples. Production payment messages generally require bank-specific implementation guidelines, complete party and account information, and validation against the applicable XSD and market profile.

## Custom adapters

A FinSpace adapter is normally just a callable:

```python
def price(record: dict[str, object]) -> dict[str, float]:
    ...
```

Keep schema values stable and perform conversion at this boundary.
