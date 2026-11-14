# makefun-food-picture-01

[![make.fun](https://make.fun/badge/food-picture-01)](https://make.fun/c/food-picture-01)

One image of the best-looking food you can draw in code: "The Golden
Smash Burger" — a glossy brioche bun with sesame seeds, melted
cheddar dripping over a char-marked patty, tomato and scalloped
lettuce, a cup of golden fries, and steam rising off the bun, on a
cream plate over a dark walnut table, captioned "FRESH OFF THE
GRILL".

## How it works

`main.py` uses only the Python standard library. It renders the scene
at 2x supersampling into a 2048x2048 RGB buffer (background gradient
and radial glow, plate, burger stack, fries, soft steam wisps and the
caption are all drawn with code: rectangles, discs, ellipses,
polygons and a 5x7 bitmap font), box-downsamples to 1024x1024, and
writes the PNG with a hand-rolled encoder. The output is
deterministic: the same bytes on every run, well under the 1 MiB
limit.

## Run

```sh
MAKEFUN_OUTPUT_DIR=/tmp/out python3 main.py
# writes /tmp/out/entry.png (1024x1024)
```

## License

MIT. See [LICENSE](LICENSE).
