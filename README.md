# Pomegranate Panic

A mobile-first HTML5 game where you place ramps to keep a rolling pomegranate from falling off the screen.

**[Play it now!](https://zeveck.github.io/pomegranatepanic)**

![Pomegranate Panic gameplay](screenshot.png)

## How to Play

1. A pomegranate rolls down ramps, starting slowly
2. Tap anywhere to place randomly-generated ramps
3. Build a path to catch the pomegranate as it falls
4. Keep it alive as long as possible - speed increases over time!
5. Game over when the pomegranate falls off the bottom

## Features

- **Mobile-first design** - Touch controls, portrait orientation, no zoom/scroll
- **Random ramp generation** - Each ramp has a random angle and length (like Tetris pieces)
- **Increasing difficulty** - Speed gradually ramps up from chill to frantic
- **Satisfying physics** - Wobble effect as the pomegranate rolls
- **Clean visuals** - Deep red pomegranate with calyx crown, wooden plank ramps

## Running the Game

Simply open `index.html` in a web browser, or serve it locally:

```bash
npx http-server -p 8080
```

Then visit `http://localhost:8080`

## Controls

- **Mobile**: Tap to place ramps, tap to restart after game over
- **Desktop**: Click to place ramps, click to restart after game over

## Tech Stack

- Single HTML file with embedded CSS and JavaScript
- Canvas API for rendering
- No external dependencies

## Version

v0.1.5
