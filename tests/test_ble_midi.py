from custom_components.mvave_tankg.ble_midi import program_change_frame


def test_program_change_frame_preset_one():
    # preset UI 1 -> programa 0, canal 0
    assert program_change_frame(program=0, channel=0) == bytes([0x80, 0x80, 0xC0, 0x00])


def test_program_change_frame_preset_five():
    assert program_change_frame(program=4, channel=0) == bytes([0x80, 0x80, 0xC0, 0x04])


def test_program_change_frame_other_channel():
    assert program_change_frame(program=2, channel=3) == bytes([0x80, 0x80, 0xC3, 0x02])


def test_program_change_masks_to_7_bits():
    # programa nunca pode estourar 7 bits no MIDI
    assert program_change_frame(program=200, channel=0)[3] == 200 & 0x7F
