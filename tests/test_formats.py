import pytest
from tp3.formats import timestamp, exports


def test_rounding_across_minute_and_hour():
    assert timestamp(59.9996) == '00:01:00,000'
    assert timestamp(3599.9996, '.') == '01:00:00.000'
    with pytest.raises(ValueError): timestamp(float('nan'))


def test_three_utf8_outputs():
    output = exports([{'start': 0, 'end': 1.2, 'text': ' Olá,\nCacoal! '}, {'start': 1.2, 'end': 2, 'text': ''}])
    assert output['txt'] == 'Olá, Cacoal!\n'
    assert output['srt'] == '1\n00:00:00,000 --> 00:00:01,200\nOlá, Cacoal!\n'
    assert output['vtt'].startswith('WEBVTT\n\n00:00:00.000 --> 00:00:01.200')
    with pytest.raises(ValueError): exports([{'start': 1, 'end': 0, 'text': 'a'}])
