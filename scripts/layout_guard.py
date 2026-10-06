"""Fit complete headline lines above the actual image boundary using font ink boxes."""

def fit_headline(lines, font_factory, *, video_top, anchor=(67, 245),
                 line_spacing=100, initial_size=82, min_size=48,
                 max_width=944, min_gap=30, tag_bottom=160, tag_gap=16):
    """Return validated positions; never crop text or move the underlying footage.

    Coordinates are pixels in the caller's canvas. Pass its actual video/photo
    top edge, not the coordinates of a different renderer's template.
    """
    if not 1 <= len(lines) <= 2 or any(not line.strip() for line in lines):
        raise ValueError("Headline needs one or two nonempty complete lines.")
    if min_gap < 0 or line_spacing <= 0 or max_width <= 0 or min_size <= 0:
        raise ValueError("Invalid headline layout bounds.")
    x, y = anchor
    sizes = list(range(int(initial_size), int(min_size) - 1, -2))
    if sizes and sizes[-1] != int(min_size):
        sizes.append(int(min_size))
    for size in sizes:
        font = font_factory(size)
        ink = [font.getbbox(line) for line in lines]
        if any(max(font.getlength(line), box[2] - box[0]) > max_width
               for line, box in zip(lines, ink)):
            continue
        step = max(line_spacing, max(box[3] - box[1] for box in ink) + 12)
        boxes = [(x + box[0], y + i * step + box[1],
                  x + box[2], y + i * step + box[3])
                 for i, box in enumerate(ink)]
        shift = min(0, video_top - min_gap - max(box[3] for box in boxes))
        boxes = [(a, b + shift, c, d + shift) for a, b, c, d in boxes]
        if min(box[1] for box in boxes) < tag_bottom + tag_gap:
            continue
        gap = video_top - max(box[3] for box in boxes)
        if gap < min_gap:
            raise ValueError("Headline overlaps the video or its required gap.")
        return {"font_size": size, "positions": [(x, y + i * step + shift)
                for i in range(len(lines))], "ink_boxes": boxes,
                "video_top": video_top, "gap_px": gap, "min_gap_px": min_gap}
    raise ValueError("Headline cannot fit above the image at a readable size; revise its layout.")
