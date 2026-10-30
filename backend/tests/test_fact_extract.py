import pytest

from backend.eval.fact_extract import extract_dates, extract_numbers


def amounts(text):
    return [h.value for h in extract_numbers(text) if h.kind == "amount"]


def days(text):
    return [h.value for h in extract_numbers(text) if h.kind == "days"]


@pytest.mark.parametrize("text,expected", [
    ("The balance is ₹65,200.", 65200),
    ("Pay Rs 65,200 today.", 65200),
    ("Pay Rs. 65200 today.", 65200),
    ("It is INR 65200.", 65200),
    ("About 65,200 rupees.", 65200),
    ("The amount is 65200.", 65200),
    ("Two and a half: 2.5 lakh.", 250000),
    ("Roughly 65 thousand.", 65000),
    ("Say 65k.", 65000),
    ("Sixty-five thousand two hundred rupees.", 65200),
    ("sixty five thousand two hundred", 65200),
    ("One lakh four thousand nine hundred and two", 104902),
    ("Pay fifty rupees.", 50),
    ("Pay a thousand soon.", 1000),
])
def test_amount_forms(text, expected):
    assert amounts(text) == [expected]


def test_days_digits_and_words():
    assert days("It is 78 days overdue.") == [78]
    assert days("Within sixty days.") == [60]
    assert amounts("It is 78 days overdue.") == []


def test_invoice_ids_phones_and_codes_are_not_amounts():
    assert amounts("Invoice INV-2026-1004, call 9876543210, UTR 123456789012.") == []


def test_plain_small_numbers_and_words_are_ignored():
    assert amounts("I have one question about three parts.") == []


@pytest.mark.parametrize("text", [
    "Pay by November 10th, 2026.", "Pay by 10th of November 2026.", "Pay by 10 November 2026.",
    "Pay by 2026-11-10.", "Pay by 10/11/2026.",
])
def test_years_in_dates_are_one_date_and_zero_amounts(text):
    assert amounts(text) == []
    found = extract_dates(text)
    assert len(found) == 1 and (found[0].year, found[0].month, found[0].day) == (2026, 11, 10)


@pytest.mark.parametrize("text,ymd", [
    ("November 10th, 2026", (2026, 11, 10)),
    ("10 November", (None, 11, 10)),
    ("10th of November", (None, 11, 10)),
    ("November tenth", (None, 11, 10)),
    ("the tenth", (None, None, 10)),
    ("the 10th", (None, None, 10)),
    ("the tenth of this month", (None, 11, 10)),
    ("the third of next month", (None, 12, 3)),
    ("2026-11-10", (2026, 11, 10)),
    ("10/11/2026", (2026, 11, 10)),
    ("10/11", (None, 11, 10)),
    ("twenty-first of November", (None, 11, 21)),
])
def test_date_forms(text, ymd):
    [h] = extract_dates(f"Pay on {text}.")
    assert (h.year, h.month, h.day) == ymd and h.valid


def test_invalid_dates_are_flagged_invalid():
    assert [h.valid for h in extract_dates("On 31/02 or February 30th.")] == [False, False]


def test_ordinary_words_are_not_dates():
    assert extract_dates("The second option, the first thing, in September and October.") == []


def test_unparsed_amounts():
    hits = extract_numbers("You owe lakhs of rupees, about ₹ something, and five six thousand.")
    assert [h.value for h in hits] == [None, None, None]


def test_wording_and_position():
    [h] = extract_numbers("Please pay sixty-five thousand two hundred rupees now.")
    assert h.snippet == "sixty-five thousand two hundred rupees"
