# Version — Apple Software Tracker

An elegant, Apple-inspired interface for tracking Apple software versions and release notes.

## Features

- 📱 Clean, modern design inspired by Apple's design language
- 🎨 Fully responsive layout that works on all devices
- 🔍 Search and filter functionality for easy navigation
- 📝 Interactive changelog drawer for release notes
- 🔄 Daily release checks from official Apple sources
- ✨ Smooth animations and transitions
- ♿ Accessible with proper ARIA labels and keyboard navigation

## Preview

View the live page: [Open index.html](index.html)

## Technologies

- Pure HTML, CSS, and JavaScript
- No external dependencies
- Responsive design with CSS Grid and Flexbox
- Custom CSS properties for theming

## Usage

Simply open `index.html` in your web browser to view the tracker.

## Automated release checks

The `Check Apple releases` GitHub Actions workflow runs every day at 06:17 UTC and can also be started manually. It checks:

- [Apple security releases](https://support.apple.com/en-us/100100) for stable operating systems and Safari
- [Apple Developer releases](https://developer.apple.com/news/releases/rss/releases.rss) for Xcode and developer betas
- [HomePod software updates](https://support.apple.com/en-us/108045) for HomePod

When `data/releases.js` changes, the workflow opens or updates an `automation/apple-release-update` pull request instead of publishing unreviewed data. The repository must allow GitHub Actions to create pull requests under **Settings > Actions > General > Workflow permissions**.

Run the checker locally with:

```sh
python scripts/check_releases.py
python -m unittest discover -s tests
```

## Customization

The design uses CSS custom properties (variables) for easy theming:

```css
:root {
  --ink: #17171a;      /* Primary text color */
  --muted: #6e6e73;    /* Secondary text color */
  --soft: #f5f5f7;     /* Light background */
  --line: #e4e4e8;     /* Border color */
  --blue: #0071e3;     /* Accent blue */
  --green: #28b47a;    /* Accent green */
}
```

## License

Free to use for personal and commercial projects.
