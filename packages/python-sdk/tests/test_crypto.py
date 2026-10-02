"""Tests for agentnet.crypto — the M1 E2EE trust-root primitives."""

import base64

import pytest

from agentnet.crypto import (
    ENCRYPTION_ALGORITHM,
    KEY_SIZE,
    AgentPublicKeys,
    SealedMessage,
    aes_gcm_decrypt,
    aes_gcm_encrypt,
    b64decode,
    b64encode,
    derive_session_key,
    generate_kem_keypair,
    generate_signing_keypair,
    key_fingerprint,
    open_message,
    seal_message,
    sign,
    verify_signature,
)

PLAINTEXT = b"the quick brown fox jumps over the lazy dog"


@pytest.fixture()
def recipient_keys() -> tuple[bytes, AgentPublicKeys]:
    kem_private, kem_public = generate_kem_keypair()
    _, sig_public = generate_signing_keypair()
    return kem_private, AgentPublicKeys(kem=kem_public, sig=sig_public)


@pytest.fixture()
def sender_keys() -> tuple[bytes, bytes]:
    sig_private, sig_public = generate_signing_keypair()
    return sig_private, sig_public


class TestKeypairs:
    def test_kem_keypair_sizes(self):
        private, public = generate_kem_keypair()
        assert len(private) == KEY_SIZE
        assert len(public) == KEY_SIZE
        assert private != public

    def test_signing_keypair_sizes(self):
        private, public = generate_signing_keypair()
        assert len(private) == KEY_SIZE
        assert len(public) == KEY_SIZE

    def test_keypairs_are_unique(self):
        p1, pub1 = generate_kem_keypair()
        p2, pub2 = generate_kem_keypair()
        assert p1 != p2
        assert pub1 != pub2


class TestSignVerify:
    def test_sign_verify_roundtrip(self, sender_keys):
        sig_private, sig_public = sender_keys
        signature = sign(sig_private, PLAINTEXT)
        assert isinstance(signature, bytes)
        assert verify_signature(sig_public, PLAINTEXT, signature)

    def test_verify_rejects_wrong_message(self, sender_keys):
        sig_private, sig_public = sender_keys
        signature = sign(sig_private, PLAINTEXT)
        assert not verify_signature(sig_public, b"tampered", signature)

    def test_verify_rejects_wrong_key(self, sender_keys):
        sig_private, _ = sender_keys
        _, other_public = generate_signing_keypair()
        signature = sign(sig_private, PLAINTEXT)
        assert not verify_signature(other_public, PLAINTEXT, signature)

    def test_verify_rejects_malformed_key(self):
        assert not verify_signature(b"\x00" * 31, PLAINTEXT, b"\x00" * 64)


class TestFingerprint:
    def test_fingerprint_is_stable(self):
        _, public = generate_kem_keypair()
        assert key_fingerprint(public) == key_fingerprint(public)

    def test_fingerprint_differs_per_key(self):
        _, pub1 = generate_kem_keypair()
        _, pub2 = generate_kem_keypair()
        assert key_fingerprint(pub1) != key_fingerprint(pub2)

    def test_fingerprint_is_hex_sha256(self):
        import hashlib

        _, public = generate_kem_keypair()
        assert key_fingerprint(public) == hashlib.sha256(public).hexdigest()


class TestKeyAgreement:
    def test_ecdh_is_symmetric(self):
        a_private, a_public = generate_kem_keypair()
        b_private, b_public = generate_kem_keypair()
        key_ab = derive_session_key(a_private, b_public)
        key_ba = derive_session_key(b_private, a_public)
        assert key_ab == key_ba
        assert len(key_ab) == 32

    def test_derived_keys_differ_for_different_peers(self):
        a_private, _ = generate_kem_keypair()
        b_private, b_public = generate_kem_keypair()
        _, c_public = generate_kem_keypair()
        assert derive_session_key(a_private, b_public) != derive_session_key(
            a_private, c_public
        )

    def test_rejects_malformed_public_key(self):
        a_private, _ = generate_kem_keypair()
        with pytest.raises(ValueError):
            derive_session_key(a_private, b"\x00" * 31)


class TestAesGcm:
    def test_encrypt_decrypt_roundtrip(self):
        key = b"\x01" * 32
        nonce = b"\x02" * 12
        aad = b"associated"
        ciphertext = aes_gcm_encrypt(key, nonce, PLAINTEXT, aad)
        assert ciphertext != PLAINTEXT
        assert aes_gcm_decrypt(key, nonce, ciphertext, aad) == PLAINTEXT

    def test_tampered_ciphertext_fails(self):
        key = b"\x01" * 32
        nonce = b"\x02" * 12
        ciphertext = bytearray(aes_gcm_encrypt(key, nonce, PLAINTEXT, b"aad"))
        ciphertext[0] ^= 0xFF
        assert aes_gcm_decrypt(key, nonce, bytes(ciphertext), b"aad") is None

    def test_wrong_aad_fails(self):
        key = b"\x01" * 32
        nonce = b"\x02" * 12
        ciphertext = aes_gcm_encrypt(key, nonce, PLAINTEXT, b"aad")
        assert aes_gcm_decrypt(key, nonce, ciphertext, b"other") is None

    def test_wrong_key_fails(self):
        nonce = b"\x02" * 12
        ciphertext = aes_gcm_encrypt(b"\x01" * 32, nonce, PLAINTEXT, b"aad")
        assert aes_gcm_decrypt(b"\x03" * 32, nonce, ciphertext, b"aad") is None

    def test_bad_key_size_rejected(self):
        with pytest.raises(ValueError):
            aes_gcm_encrypt(b"\x01" * 16, b"\x02" * 12, PLAINTEXT, b"aad")

    def test_bad_nonce_size_rejected(self):
        with pytest.raises(ValueError):
            aes_gcm_encrypt(b"\x01" * 32, b"\x02" * 8, PLAINTEXT, b"aad")


class TestAgentPublicKeys:
    def test_json_roundtrip(self):
        _, kem_pub = generate_kem_keypair()
        _, sig_pub = generate_signing_keypair()
        keys = AgentPublicKeys(kem=kem_pub, sig=sig_pub)
        restored = AgentPublicKeys.from_json_dict(keys.to_json_dict())
        assert restored == keys
        assert restored.version == 1

    def test_json_shape(self):
        _, kem_pub = generate_kem_keypair()
        _, sig_pub = generate_signing_keypair()
        data = AgentPublicKeys(kem=kem_pub, sig=sig_pub).to_json_dict()
        assert set(data) == {"kem", "sig", "v"}
        assert data["v"] == 1
        # Wire fields are standard-alphabet base64 of 32 raw bytes
        assert len(b64decode(data["kem"])) == 32
        assert len(b64decode(data["sig"])) == 32

    def test_from_json_rejects_bad_base64(self):
        with pytest.raises(ValueError):
            AgentPublicKeys.from_json_dict({"kem": "!!!not-base64!!!", "sig": "A" * 44})

    def test_from_json_rejects_wrong_length(self):
        short = b64encode(b"\x00" * 31)
        with pytest.raises(ValueError):
            AgentPublicKeys.from_json_dict({"kem": short, "sig": b64encode(b"\x00" * 32)})

    def test_from_json_rejects_unknown_version(self):
        _, kem_pub = generate_kem_keypair()
        _, sig_pub = generate_signing_keypair()
        data = AgentPublicKeys(kem=kem_pub, sig=sig_pub).to_json_dict()
        data["v"] = 99
        with pytest.raises(ValueError):
            AgentPublicKeys.from_json_dict(data)

    def test_from_json_rejects_non_object(self):
        with pytest.raises(ValueError):
            AgentPublicKeys.from_json_dict(["not", "a", "dict"])  # type: ignore[arg-type]

    def test_fingerprint_matches_kem_key(self):
        _, kem_pub = generate_kem_keypair()
        _, sig_pub = generate_signing_keypair()
        keys = AgentPublicKeys(kem=kem_pub, sig=sig_pub)
        assert keys.fingerprint == key_fingerprint(kem_pub)


class TestSealOpen:
    def test_seal_open_roundtrip(self, recipient_keys, sender_keys):
        kem_private, recipient_public = recipient_keys
        sig_private, sig_public = sender_keys
        sealed = seal_message(
            PLAINTEXT,
            recipient_public_keys=recipient_public,
            sender_signing_private_key=sig_private,
        )
        opened = open_message(
            sealed,
            recipient_kem_private_key=kem_private,
            sender_signing_public_key=sig_public,
        )
        assert opened == PLAINTEXT

    def test_sealed_fields(self, recipient_keys, sender_keys):
        kem_private, recipient_public = recipient_keys
        sig_private, _ = sender_keys
        sealed = seal_message(
            PLAINTEXT,
            recipient_public_keys=recipient_public,
            sender_signing_private_key=sig_private,
        )
        assert len(sealed.nonce) == 12
        assert sealed.key_id == recipient_public.fingerprint
        assert len(sealed.ephemeral_kem_public) == 32
        assert sealed.ciphertext != PLAINTEXT
        # Random per seal: two seals of the same plaintext differ
        sealed2 = seal_message(
            PLAINTEXT,
            recipient_public_keys=recipient_public,
            sender_signing_private_key=sig_private,
        )
        assert sealed.ciphertext != sealed2.ciphertext
        assert sealed.nonce != sealed2.nonce

    def test_open_rejects_wrong_recipient(
        self, recipient_keys, sender_keys
    ):
        _, recipient_public = recipient_keys
        sig_private, sig_public = sender_keys
        sealed = seal_message(
            PLAINTEXT,
            recipient_public_keys=recipient_public,
            sender_signing_private_key=sig_private,
        )
        other_private, _ = generate_kem_keypair()
        assert (
            open_message(
                sealed,
                recipient_kem_private_key=other_private,
                sender_signing_public_key=sig_public,
            )
            is None
        )

    def test_open_rejects_wrong_sender_key(
        self, recipient_keys, sender_keys
    ):
        kem_private, recipient_public = recipient_keys
        sig_private, _ = sender_keys
        sealed = seal_message(
            PLAINTEXT,
            recipient_public_keys=recipient_public,
            sender_signing_private_key=sig_private,
        )
        _, other_sig_public = generate_signing_keypair()
        assert (
            open_message(
                sealed,
                recipient_kem_private_key=kem_private,
                sender_signing_public_key=other_sig_public,
            )
            is None
        )

    def test_open_rejects_tampered_ciphertext(
        self, recipient_keys, sender_keys
    ):
        kem_private, recipient_public = recipient_keys
        sig_private, sig_public = sender_keys
        sealed = seal_message(
            PLAINTEXT,
            recipient_public_keys=recipient_public,
            sender_signing_private_key=sig_private,
        )
        tampered = SealedMessage(
            ciphertext=bytes(c ^ 0xFF for c in sealed.ciphertext),
            nonce=sealed.nonce,
            key_id=sealed.key_id,
            ephemeral_kem_public=sealed.ephemeral_kem_public,
            signature=sealed.signature,
            aad=sealed.aad,
        )
        assert (
            open_message(
                tampered,
                recipient_kem_private_key=kem_private,
                sender_signing_public_key=sig_public,
            )
            is None
        )

    def test_open_rejects_tampered_signature(
        self, recipient_keys, sender_keys
    ):
        kem_private, recipient_public = recipient_keys
        sig_private, sig_public = sender_keys
        sealed = seal_message(
            PLAINTEXT,
            recipient_public_keys=recipient_public,
            sender_signing_private_key=sig_private,
        )
        tampered = SealedMessage(
            ciphertext=sealed.ciphertext,
            nonce=sealed.nonce,
            key_id=sealed.key_id,
            ephemeral_kem_public=sealed.ephemeral_kem_public,
            signature=b"\x00" * 64,
            aad=sealed.aad,
        )
        assert (
            open_message(
                tampered,
                recipient_kem_private_key=kem_private,
                sender_signing_public_key=sig_public,
            )
            is None
        )

    def test_extra_aad_is_authenticated(self, recipient_keys, sender_keys):
        kem_private, recipient_public = recipient_keys
        sig_private, sig_public = sender_keys
        sealed = seal_message(
            PLAINTEXT,
            recipient_public_keys=recipient_public,
            sender_signing_private_key=sig_private,
            extra_aad={"conversation_id": "conv-42", "from": "AN-1"},
        )
        # Original aad roundtrips
        opened = open_message(
            sealed,
            recipient_kem_private_key=kem_private,
            sender_signing_public_key=sig_public,
        )
        assert opened == PLAINTEXT
        assert sealed.aad["conversation_id"] == "conv-42"
        # Mutating the aad breaks the AEAD authentication
        tampered = SealedMessage(
            ciphertext=sealed.ciphertext,
            nonce=sealed.nonce,
            key_id=sealed.key_id,
            ephemeral_kem_public=sealed.ephemeral_kem_public,
            signature=sealed.signature,
            aad={**sealed.aad, "conversation_id": "conv-evil"},
        )
        assert (
            open_message(
                tampered,
                recipient_kem_private_key=kem_private,
                sender_signing_public_key=sig_public,
            )
            is None
        )


class TestEnvelopeFields:
    def test_envelope_roundtrip_preserves_seal(
        self, recipient_keys, sender_keys
    ):
        kem_private, recipient_public = recipient_keys
        sig_private, sig_public = sender_keys
        sealed = seal_message(
            PLAINTEXT,
            recipient_public_keys=recipient_public,
            sender_signing_private_key=sig_private,
        )
        fields = sealed.to_envelope_fields()
        assert set(fields) == {"security", "encrypted_payload", "aad"}
        security = fields["security"]
        assert security["mode"] == "e2ee"
        assert security["encryption"] == ENCRYPTION_ALGORITHM
        assert security["key_id"] == recipient_public.fingerprint
        # nonce + ciphertext are non-empty standard base64
        base64.standard_b64decode(security["nonce"].encode("ascii"))
        assert fields["encrypted_payload"]
        base64.standard_b64decode(fields["encrypted_payload"].encode("ascii"))
        assert isinstance(fields["aad"], dict)
        assert fields["aad"]["sig"]

        restored = SealedMessage.from_envelope_fields(
            {
                "security": security,
                "encrypted_payload": fields["encrypted_payload"],
                "aad": dict(fields["aad"]),
            }
        )
        assert (
            open_message(
                restored,
                recipient_kem_private_key=kem_private,
                sender_signing_public_key=sig_public,
            )
            == PLAINTEXT
        )
