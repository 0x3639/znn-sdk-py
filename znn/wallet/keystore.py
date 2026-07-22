from bip_utils import Bip32Ed25519Slip
from mnemonic import Mnemonic

from .keypair import KeyPair


class KeyStore:
    def __init__(self, mnemonic: str, passphrase: str = ""):
        mnemonic_obj = Mnemonic("english")
        self.mnemonic = mnemonic
        self.seed = mnemonic_obj.to_seed(mnemonic, passphrase=passphrase).hex()
        self.entropy = mnemonic_obj.to_entropy(mnemonic).hex()

    def get_key_pair(self, account: int = 0):
        if not isinstance(account, int) or isinstance(account, bool) or account < 0:
            raise ValueError("account must be a non-negative integer")
        # BIP44 https://github.com/bitcoin/bips/blob/master/bip-0044.mediawiki
        # m / purpose' / coin_type' / account' / change / address_index
        path = f"m/44'/73404'/{account}'"

        # TODO: Publish a python package with just Bip32Ed25519Slip class to
        # minimize dependency tree and then get rid of bip_utils package
        # Spent a long time playing with other packages and manual scripts, no good
        # So falling back to bip_utils package for now
        bip32_mst_ctx = Bip32Ed25519Slip.FromSeed(bytes.fromhex(self.seed))
        bip32_der_ctx = bip32_mst_ctx.DerivePath(path)
        private_key_hex = bip32_der_ctx.PrivateKey().Raw().ToHex()
        return KeyPair(private_key_hex)

    @staticmethod
    def new_random(passphrase: str = ""):
        mnemo = Mnemonic("english")
        words = mnemo.generate(strength=256)
        return KeyStore(words, passphrase)

    @staticmethod
    def from_mnemonic(mnemonic: str, passphrase: str = ""):
        return KeyStore(mnemonic, passphrase)

    @staticmethod
    def from_entropy(entropy: str | bytes, passphrase: str = ""):
        raw = bytes.fromhex(entropy) if isinstance(entropy, str) else bytes(entropy)
        if len(raw) not in {16, 32}:
            raise ValueError("SDK entropy import requires exactly 16 or 32 bytes")
        mnemonic = Mnemonic("english").to_mnemonic(raw)
        return KeyStore(mnemonic, passphrase)

    def clear(self) -> None:
        """Drop mnemonic/seed references.

        Best-effort only: the original immutable strings remain in interpreter
        memory until garbage collected. See ``KeyPair`` for details.
        """
        self.mnemonic = ""
        self.seed = ""
        self.entropy = ""
