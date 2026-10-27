from contabil.pilot_samples import _ACTIVITY_TEXT, activity_amount


def test_october_activity_amounts_differ_by_company() -> None:
    amounts = {story: activity_amount(story, "bank", 10) for story in _ACTIVITY_TEXT}
    assert len(amounts) == 5
    assert len(set(amounts.values())) == 5


def test_activity_texts_name_the_trade() -> None:
    descriptions = {text["bank"] for text in _ACTIVITY_TEXT.values()}
    assert len(descriptions) == 5
    assert len({text["capital_amount"] for text in _ACTIVITY_TEXT.values()}) == 5
