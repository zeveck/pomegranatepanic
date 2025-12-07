# Pomegranate Panic

A mobile-first HTML5 game where you place ramps to keep a rolling pomegranate from falling off the screen.

**[Play it now!](https://zeveck.github.io/pomegranatepanic)**

![Pomegranate Panic gameplay](screenshot.png)

## How to Play

1. Tap/click to place ramps and catch the rolling pomegranate
2. Big drops trigger bounces for bonus points - chain them for combos!
3. Survive as long as possible as speed increases

## Features

- Mobile-first touch controls with drag-to-place and ghost preview
- Random ramp generation (angle and length vary like Tetris pieces)
- Bounce and combo system for bonus points
- Increasing speed over time

## Running the Game

Simply open `index.html` in a web browser, or serve it locally:

```bash
npx http-server -p 8080
```

Then visit `http://localhost:8080`

## Controls

- **Mobile**: Drag to position, release to place. Tap to restart.
- **Desktop**: Click to place. Click to restart.

## Tech Stack

- Single HTML file with embedded CSS and JavaScript
- Canvas API for rendering
- No external dependencies

## Version

v0.1.6
