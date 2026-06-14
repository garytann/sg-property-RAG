from typing import Dict, Optional


def calculate_gross_yield(price: float, monthly_rent: float) -> Dict[str, float]:
    annual_rent = monthly_rent * 12
    return {
        "annual_rent": round(annual_rent, 2),
        "gross_yield_percent": round((annual_rent / price) * 100, 2) if price else 0.0,
    }


def calculate_psf(price: float, floor_area_sqft: float) -> Dict[str, float]:
    return {
        "psf": round(price / floor_area_sqft, 2) if floor_area_sqft else 0.0,
    }


def calculate_buyer_stamp_duty(price: float) -> Dict[str, float]:
    """Residential BSD estimate. Verify current rates before real decisions."""
    brackets = [
        (180_000, 0.01),
        (180_000, 0.02),
        (640_000, 0.03),
        (500_000, 0.04),
        (1_500_000, 0.05),
        (None, 0.06),
    ]

    remaining = price
    duty = 0.0
    for bracket_amount, rate in brackets:
        if remaining <= 0:
            break
        taxable = remaining if bracket_amount is None else min(remaining, bracket_amount)
        duty += taxable * rate
        remaining -= taxable

    return {
        "buyer_stamp_duty": round(duty, 2),
        "note": "Illustrative residential BSD estimate. Verify current IRAS rates before using for decisions.",
    }


def estimate_monthly_mortgage(
    principal: float,
    annual_interest_rate: float,
    tenure_years: int,
) -> Dict[str, float]:
    monthly_rate = annual_interest_rate / 100 / 12
    number_of_payments = tenure_years * 12

    if number_of_payments <= 0:
        return {"monthly_payment": 0.0}

    if monthly_rate == 0:
        monthly_payment = principal / number_of_payments
    else:
        monthly_payment = (
            principal
            * monthly_rate
            * (1 + monthly_rate) ** number_of_payments
            / ((1 + monthly_rate) ** number_of_payments - 1)
        )

    return {
        "monthly_payment": round(monthly_payment, 2),
        "principal": round(principal, 2),
        "annual_interest_rate": annual_interest_rate,
        "tenure_years": tenure_years,
    }


def calculate_property_metrics(property_row: Dict[str, Optional[float]]) -> Dict[str, float]:
    price = float(property_row.get("asking_price") or 0)
    sqft = float(property_row.get("floor_area_sqft") or 0)
    monthly_rent = float(property_row.get("monthly_rent_estimate") or 0)

    return {
        **calculate_psf(price, sqft),
        **calculate_gross_yield(price, monthly_rent),
    }

