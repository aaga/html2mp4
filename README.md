# HTML2MP4

This project was made for the first-ever [BrowserJam](https://github.com/BrowserJam/browserjam). As such it is a hacky, barely-functional, forever-beta piece of code. It is hyper-optimized to render specifically this page: https://info.cern.ch/hypertext/WWW/TheProject.html

![](/DEMOS/Star%20Wars/The%20World%20Wide%20Web%20project.mp4)

## Overview
This is (nominally) a "browser" that takes an HTML file and outputs a `.mp4` movie (with subtitles) that is representative of the original HTML.

For the `BASIC` theme, this amounts to a slideshow: [example output](/DEMOS/Basic%20(no%20sound)/The%20World%20Wide%20Web%20project.mp4)

For the `BASIC_WITH_SOUND` theme, the slides are read aloud by a Text-To-Speech voice: [example output](/DEMOS/Basic%20(with%20TTS)/The%20World%20Wide%20Web%20project.mp4)

For the `STAR_WARS` theme, the browser instead produces a creative rendition of a Star Wars movie with an opening crawl and voice-cloned characters speaking the lines: [example output](/DEMOS/Star%20Wars/The%20World%20Wide%20Web%20project.mp4)

The `STAR_WARS` theme also has an option for `--darkmode` which is the same as above, except the chosen characters are aligned with the dark side of the Force: [example output](/DEMOS/Star%20Wars%20(Dark%20Mode)/The%20World%20Wide%20Web%20project%20(Dark%20Mode).mp4)

## How it works
I use [BeautifulSoup](https://www.crummy.com/software/BeautifulSoup/) to parse the HTML.

I then do a "layout" step to produce a Shot List of sorts that I can use to render the movie.

I stitch the movie together using the [MoviePy](https://zulko.github.io/moviepy/) library, which is essentially a wrapper around the commonly-used `ffmpeg` and ImageMagick tools.

I add the spoken lines using the open-source [Coqui TTS](https://github.com/coqui-ai/TTS). For the Star Wars theme, I use the magical `xtts_v2` model that is capable of voice-cloning with just a short sample of speaker audio.

## Usage
This project uses [uv](https://github.com/astral-sh/uv), so you should be able to install all dependencies and run the script with `uv run html2mp4.py $ARGS` (see below for args).

Note that the TTS models will take some time and space to download, and audio synthesis can be very slow depending on your machine.

Note that if you want to generate the Star Wars opening crawl, you will need to manually hotfix a line in the MoviePy library as described [here](https://github.com/Zulko/moviepy/issues/1205#issuecomment-636353519).

```
usage: uv run html2mp4.py [-h] [--theme THEME] [--darkmode] filename

Render HTML files to MP4 movies with subtitles

arguments:
  filename       Path to HTML file

options:
  --theme THEME  Choose from BASIC, BASIC_WITH_SOUND, or STAR_WARS. Defaults to BASIC
  --darkmode     Whether to enable dark mode (only works for Star Wars theme)
```

## Disclaimer
I do not own any of the Star Wars-related video and audio assets that are hosted in this repo. I am using them here for non-commercial purposes only.