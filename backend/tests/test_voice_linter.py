import pytest

from backend.eval.voice_linter import (
    count_by_category,
    count_sentences,
    lint_code_token,
    lint_digit_amount,
    lint_long_turn,
    lint_numeric_date,
    lint_symbols_markdown,
    lint_transcript,
    lint_unspelled_contact,
)
from backend.tests.eval_helpers import make_transcript


def n(fn, text):
    return len(fn(0, text))


# --- symbols_markdown ---------------------------------------------------------
@pytest.mark.parametrize("text", [
    "The balance is ₹500.", "That is $5.", "Bold **word** here.", "# Heading",
    "About 50% of it.", "Use cash and/or card.", "Done 😊", "* first item",
    "- first item", "1. first item", "• first item", "See [here](http://x.y)",
    "Use `code` please.",
])
def test_symbols_flagged(text):
    assert n(lint_symbols_markdown, text) >= 1


@pytest.mark.parametrize("text", [
    "I can help you pay on November tenth.", "Mr. Chauhan, thank you.",
    "The date is 10/11 for now.",  # slash between digits belongs to numeric_date
    "Fifty percent of it, please.", "Can you confirm, please?",
])
def test_symbols_not_flagged(text):
    assert n(lint_symbols_markdown, text) == 0


# --- long_turn ----------------------------------------------------------------
def test_two_sentences_ok_three_flagged():
    assert n(lint_long_turn, "Hello there. How are you today?") == 0
    assert n(lint_long_turn, "Hello there. How are you? I am calling about your invoice.") == 1


def test_multiple_paragraphs_flagged():
    assert n(lint_long_turn, "Hello there.\n\nHow are you?") == 1


def test_titles_and_decimals_are_not_sentence_ends():
    assert count_sentences("Hello Mr. Arjun Chauhan. Is this a good time?") == 2
    assert count_sentences("Dr. Rao, you owe 2.5 lakh. Can you pay?") == 2


def test_exclamations_and_ellipsis():
    assert count_sentences("Thanks! Goodbye... See you.") == 3


# --- digit_amount ---------------------------------------------------------------
@pytest.mark.parametrize("text", [
    "The balance is 65,200 rupees.", "Please pay Rs 500.", "That is INR 65200.",
    "About 2.5 lakh is due.", "You owe 500 rupees.", "The amount is 65200.",
])
def test_digit_amount_flagged(text):
    assert n(lint_digit_amount, text) == 1


@pytest.mark.parametrize("text", [
    "The balance is sixty-five thousand two hundred rupees.",
    "It is seventy eight days overdue.", "It is 78 days overdue.",
    "Call 3 times.", "Please pay by November tenth.",
])
def test_digit_amount_not_flagged(text):
    assert n(lint_digit_amount, text) == 0


@pytest.mark.parametrize("text", [
    "Please pay by November 10th, 2026.", "Please pay by 10th of November 2026.",
    "Please pay by 10 November 2026.", "Please pay by November 10, 2026.",
    "Please pay on 2026-11-10.", "Please pay on 10/11/2026.",
])
def test_years_in_dates_are_never_digit_amounts(text):
    assert n(lint_digit_amount, text) == 0


def test_real_amount_next_to_a_year_is_flagged_once():
    found = lint_digit_amount(0, "Pay ₹65,200 by November 10th, 2026.")
    assert len(found) == 1 and "65,200" in found[0].snippet


def test_codes_and_phones_are_not_digit_amounts():
    assert n(lint_digit_amount, "Invoice INV-2026-1004 and call 9876543210.") == 0


# --- numeric_date -------------------------------------------------------------
@pytest.mark.parametrize("text", [
    "Pay by 2026-11-10.", "Pay by 10/11/2026.", "Pay by 10/11.", "Pay by 10-11-2026.",
    "Pay by 10.11.2026.",
])
def test_numeric_date_flagged(text):
    assert n(lint_numeric_date, text) == 1


@pytest.mark.parametrize("text", [
    "Pay by November tenth.", "Pay by November 10th, 2026.", "Pay by the tenth.",
    "Invoice INV-2026-1004 is overdue.", "It is 78 days overdue.", "Call 9876543210.",
])
def test_numeric_date_not_flagged(text):
    assert n(lint_numeric_date, text) == 0


# --- code_token ---------------------------------------------------------------
@pytest.mark.parametrize("text", [
    "Your invoice INV-2026-1004 is overdue.", "The UTR is 123456789012.", "Ref AB-12 noted.",
])
def test_code_token_flagged(text):
    assert n(lint_code_token, text) == 1


@pytest.mark.parametrize("text", [
    "Your invoice is overdue.", "Call 9876543210.", "Pay by 2026-11-10.",
    "The invoice I N V dash two zero two six dash one zero zero four.",
])
def test_code_token_not_flagged(text):
    assert n(lint_code_token, text) == 0


# --- unspelled_contact ----------------------------------------------------------
@pytest.mark.parametrize("text", [
    "Email arjun@example.com please.", "Call 9876543210.", "Call +91 98765 43210.",
    "Call 98765-43210.", "Visit example.com today.",
])
def test_unspelled_contact_flagged(text):
    assert n(lint_unspelled_contact, text) == 1


@pytest.mark.parametrize("text", [
    "Email arjun at example dot com please.",
    "Call nine eight seven six five four three two one zero.",
    "The balance is 65200 rupees.",
])
def test_unspelled_contact_not_flagged(text):
    assert n(lint_unspelled_contact, text) == 0


# --- whole transcript -----------------------------------------------------------
def test_lint_transcript_only_checks_agent_turns_and_skips_empty_text():
    t = make_transcript([
        ("agent", "Pay ₹500 by 10/11."),
        ("debtor", "I'll pay ₹500 by 10/11, 100% sure!"),
        ("agent", ""),
    ])
    found = lint_transcript(t)
    assert {v.turn for v in found} == {0}
    assert {v.category for v in found} == {"symbols_markdown", "digit_amount", "numeric_date"}


def test_count_by_category_has_every_category():
    counts = count_by_category(lint_transcript(make_transcript([("agent", "Pay ₹500.")])))
    assert counts["symbols_markdown"] == 1 and counts["digit_amount"] == 1
    assert set(counts) == {"symbols_markdown", "long_turn", "digit_amount", "numeric_date",
                           "code_token", "unspelled_contact"}
