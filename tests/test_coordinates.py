"""Tests for the portrait→landscape touch coordinate transform."""
import ui


def test_origin():
    assert ui.to_landscape(0, 0) == (249, 0)


def test_portrait_top_right():
    # Portrait (tx=0, ty=249) maps to landscape top-left corner
    assert ui.to_landscape(0, 249) == (0, 0)


def test_portrait_bottom_left():
    assert ui.to_landscape(121, 0) == (249, 121)


def test_portrait_bottom_right():
    assert ui.to_landscape(121, 249) == (0, 121)


def test_midpoint():
    lx, ly = ui.to_landscape(60, 125)
    assert lx == 249 - 125
    assert ly == 60


def test_formula():
    # lx = 249 - ty,  ly = tx
    for tx, ty in [(0, 0), (50, 100), (121, 249), (10, 200)]:
        lx, ly = ui.to_landscape(tx, ty)
        assert lx == 249 - ty
        assert ly == tx


def test_four_rotations_identity():
    # Applying the transform 4 times returns the original coordinates
    tx, ty = 50, 100
    x, y = tx, ty
    for _ in range(4):
        x, y = ui.to_landscape(x, y)
    assert (x, y) == (tx, ty)
