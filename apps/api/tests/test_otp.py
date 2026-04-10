"""Tests for OTP generation."""

from app.services.otp import generate_otp, OTP_LENGTH


def test_generate_otp_length():
    otp = generate_otp()
    assert len(otp) == OTP_LENGTH


def test_generate_otp_digits_only():
    otp = generate_otp()
    assert otp.isdigit()


def test_generate_otp_unique():
    otps = {generate_otp() for _ in range(50)}
    assert len(otps) > 1  # statistically impossible to get 50 identical 6-digit codes
