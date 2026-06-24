class DonorDomainError(Exception):
    """Base exception for all donor-related business logic errors."""
    def __init__(self, message: str, code: str = "donor_error"):
        self.message = message
        self.code = code
        super().__init__(message)


class DonorNotFoundError(DonorDomainError):
    def __init__(self, donor_id: str):
        super().__init__(
            message=f"Donor with ID {donor_id} not found.",
            code="donor_not_found",
        )


class DuplicateDonorError(DonorDomainError):
    def __init__(self, phone: str):
        super().__init__(
            message=f"A donor with phone {phone} already exists.",
            code="duplicate_donor",
        )


class IneligibleDonorError(DonorDomainError):
    def __init__(self, message: str = "Donor is currently ineligible for donation"):
        super().__init__(
            message=message,
            code="donor_ineligible",
        )