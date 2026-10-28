# erc4626-vault-sim

An ERC-4626 tokenized vault simulator in pure Python — no dependencies.

A vault holds an underlying asset and issues shares to depositors. Shares
are priced by total assets / total supply, so yield earned by the vault
raises the value of every share without minting new ones.

## Features

- `deposit` / `mint` / `withdraw` / `redeem` with ERC-4626 conversion math
- `preview_*` helpers and per-user `max_*` limits
- Virtual share/asset offset, blunting the first-depositor inflation attack
- `yield_()` to simulate vault earnings, `donate()` for direct donations
- Rounding always favours the vault (floor division on user payouts)

## Usage

```python
from vault import Vault

v = Vault("USDC Vault")
v.deposit("alice", 1000)
v.deposit("bob", 1000)
v.yield_(200)              # vault earns 10%
print(v.share_price())     # 1.1
print(v.redeem("alice", v.balance_of("alice")))  # 1100
```

## Run

```sh
python3 vault.py            # demo
python3 vault.py --test     # doctests
```

## How the math works

```
shares = assets * (total_supply + 10**offset) // (total_assets + 1)
assets = shares * (total_assets + 1) // (total_supply + 10**offset)
```

The `+1` virtual asset and `10**offset` virtual shares keep the very first
deposit from being rounded to zero shares, which is what makes the classic
inflation attack (donate before anyone deposits, then dilute later
depositors) unprofitable.
