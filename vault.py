"""ERC-4626 tokenized vault simulator in pure Python.

A vault holds an underlying asset (e.g. a stablecoin) and issues shares to
depositors.  Shares are priced by the vault's total assets divided by the
total share supply, so yield earned by the vault (a ``yield()`` call) raises
the value of every share without minting new ones.

The conversion math follows the ERC-4626 reference implementation, using a
virtual share/asset offset so the very first depositor cannot be diluted by
a rounding (inflation) attack::

    shares = assets * (total_supply + 10**offset) // (total_assets + 1)
    assets = shares * (total_assets + 1) // (total_supply + 10**offset)

with ``offset = 0`` here (one virtual share, one virtual asset unit).

>>> from vault import Vault
>>> v = Vault("USDC Vault")
>>> v.deposit("alice", 1000)
1000
>>> v.deposit("bob", 1000)
1000
>>> v.total_assets(), v.total_supply()
(2000, 2000)
>>> v.yield_(200)  # the vault earns 10% on its holdings
>>> v.share_price()
1.1
>>> v.convert_to_assets(v.balance_of("alice"))
1099
>>> v.withdraw("alice", 1099)
1099
>>> v.balance_of("alice")
0
>>> v.total_assets(), v.total_supply()
(1101, 1000)

Minting a fixed number of shares instead of depositing assets:

>>> v = Vault("Vault")
>>> v.mint("carol", 500)
500
>>> v.total_assets(), v.total_supply()
(500, 500)
>>> v.redeem("carol", 500)
500

Rounding always favours the vault (floor division), never the user:

>>> v = Vault("Vault")
>>> v.deposit("dave", 3)
3
>>> v.deposit("erin", 1)
1
>>> v.yield_(1)  # assets 5, supply 4
>>> v.convert_to_shares(1)
0
>>> v.max_withdraw("erin")
1

First-depositor inflation attack is blunted by the virtual offset: a
donation made before anyone else deposits cannot steal later deposits.

>>> v = Vault("Vault")
>>> v.donate(1)  # attacker donates 1 unit, then deposits 2
>>> v.deposit("attacker", 2)
1
>>> v.deposit("victim", 1000)
500
>>> v.convert_to_assets(v.balance_of("victim"))
1000

Errors are plain ValueErrors:

>>> v = Vault("Vault")
>>> v.deposit("x", 0)
Traceback (most recent call last):
...
ValueError: deposit must be positive
>>> v.withdraw("x", 1)
Traceback (most recent call last):
...
ValueError: insufficient shares
"""

__all__ = ["Vault"]


class Vault:
    """A single-asset ERC-4626-style vault."""

    def __init__(self, name, decimals_offset=0):
        self.name = name
        self.offset = decimals_offset
        self._assets = 0
        self._supply = 0
        self._shares = {}

    # -- accounting -----------------------------------------------------

    def total_assets(self):
        """Total underlying assets held by the vault."""
        return self._assets

    def total_supply(self):
        """Total shares outstanding."""
        return self._supply

    def balance_of(self, user):
        """Shares held by ``user``."""
        return self._shares.get(user, 0)

    def share_price(self):
        """Assets per share as a float (1.0 for an empty vault)."""
        if self._supply == 0:
            return 1.0
        return self._assets / self._supply

    # -- conversion -----------------------------------------------------

    def convert_to_shares(self, assets):
        """Shares minted for ``assets`` of the underlying token."""
        virtual_supply = self._supply + 10 ** self.offset
        virtual_assets = self._assets + 1
        return assets * virtual_supply // virtual_assets

    def convert_to_assets(self, shares):
        """Underlying assets redeemable for ``shares``."""
        virtual_supply = self._supply + 10 ** self.offset
        virtual_assets = self._assets + 1
        return shares * virtual_assets // virtual_supply

    def preview_deposit(self, assets):
        """Shares a deposit of ``assets`` would mint."""
        return self.convert_to_shares(assets)

    def preview_mint(self, shares):
        """Assets a mint of ``shares`` would require."""
        virtual_supply = self._supply + 10 ** self.offset
        virtual_assets = self._assets + 1
        # Round up: minting must be fully backed.
        return -(-shares * virtual_assets // virtual_supply)

    def preview_withdraw(self, assets):
        """Shares a withdrawal of ``assets`` would burn (rounded up)."""
        virtual_supply = self._supply + 10 ** self.offset
        virtual_assets = self._assets + 1
        return -(-assets * virtual_supply // virtual_assets)

    def preview_redeem(self, shares):
        """Assets a redemption of ``shares`` would return."""
        return self.convert_to_assets(shares)

    # -- limits ---------------------------------------------------------

    def max_deposit(self, user):
        """No per-user cap in this simulator."""
        return None

    def max_mint(self, user):
        """No per-user cap in this simulator."""
        return None

    def max_withdraw(self, user):
        """Most assets ``user`` can withdraw right now."""
        return self.convert_to_assets(self.balance_of(user))

    def max_redeem(self, user):
        """Most shares ``user`` can redeem right now."""
        return self.balance_of(user)

    # -- actions --------------------------------------------------------

    def deposit(self, user, assets):
        """Deposit ``assets`` and mint the corresponding shares."""
        if assets <= 0:
            raise ValueError("deposit must be positive")
        shares = self.convert_to_shares(assets)
        if shares == 0:
            raise ValueError("deposit too small to mint a share")
        self._assets += assets
        self._supply += shares
        self._shares[user] = self.balance_of(user) + shares
        return shares

    def mint(self, user, shares):
        """Mint exactly ``shares`` in exchange for the required assets."""
        if shares <= 0:
            raise ValueError("mint must be positive")
        assets = self.preview_mint(shares)
        self._assets += assets
        self._supply += shares
        self._shares[user] = self.balance_of(user) + shares
        return assets

    def withdraw(self, user, assets):
        """Burn shares and return ``assets`` of the underlying token."""
        if assets <= 0:
            raise ValueError("withdraw must be positive")
        shares = self.preview_withdraw(assets)
        if shares > self.balance_of(user):
            raise ValueError("insufficient shares")
        self._assets -= assets
        self._supply -= shares
        self._shares[user] -= shares
        return assets

    def redeem(self, user, shares):
        """Burn ``shares`` and return the corresponding assets."""
        if shares <= 0:
            raise ValueError("redeem must be positive")
        if shares > self.balance_of(user):
            raise ValueError("insufficient shares")
        assets = self.convert_to_assets(shares)
        self._assets -= assets
        self._supply -= shares
        self._shares[user] -= shares
        return assets

    # -- vault events ---------------------------------------------------

    def yield_(self, amount):
        """Simulate yield: assets grow, share supply stays fixed."""
        if amount < 0:
            raise ValueError("yield cannot be negative")
        self._assets += amount

    def donate(self, amount):
        """Direct donation to the vault (no shares minted)."""
        if amount <= 0:
            raise ValueError("donation must be positive")
        self._assets += amount


def _demo():
    v = Vault("USDC Vault")
    print(f"{v.name}: alice deposits 1000, bob deposits 1000")
    v.deposit("alice", 1000)
    v.deposit("bob", 1000)
    print(f"assets={v.total_assets()} supply={v.total_supply()}")
    v.yield_(200)
    print(f"after 200 yield: share price={v.share_price():.2f}")
    print(f"alice redeems all -> {v.redeem('alice', v.balance_of('alice'))}")


if __name__ == "__main__":
    import sys

    if "--test" in sys.argv:
        import doctest

        sys.exit(doctest.testmod(verbose=False).failed)
    _demo()
