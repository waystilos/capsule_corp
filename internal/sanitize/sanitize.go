package sanitize

import (
	"regexp"
	"strings"
	"unicode"
)

var ansiRegex = regexp.MustCompile(`\x1b\][^\x07\x1b]*(?:\x07|\x1b\\)|\x1b\[[0-?]*[ -/]*[@-~]|\x1b[@-Z\\-_]`)

var fillerRunes = map[rune]bool{
	0x034F: true, // Combining Grapheme Joiner
	0x115F: true, // Hangul Choseong Filler
	0x1160: true, // Hangul Jungseong Filler
	0x17B4: true, // Khmer Vowel Inherent Aq
	0x17B5: true, // Khmer Vowel Inherent Aa
	0x180E: true, // Mongolian Vowel Separator
	0x2800: true, // Braille Pattern Blank
	0x3164: true, // Hangul Filler
	0xFFA0: true, // Halfwidth Hangul Filler
}

func isHidden(r rune) bool {
	if (r >= 0xE0000 && r <= 0xE007F) || (r >= 0xE0100 && r <= 0xE01EF) {
		return true
	}
	if fillerRunes[r] {
		return true
	}
	if unicode.Is(unicode.Cf, r) || unicode.Is(unicode.Co, r) {
		return true
	}
	return false
}

// Scrub returns text with ANSI escape codes and invisible/format characters removed.
func Scrub(text string, keepNewlines bool, controlToSpace bool) string {
	if text == "" {
		return ""
	}
	cleaned := ansiRegex.ReplaceAllString(text, "")
	cleaned = strings.ReplaceAll(cleaned, "\r\n", "\n")
	cleaned = strings.ReplaceAll(cleaned, "\r", "\n")

	var sb strings.Builder
	sb.Grow(len(cleaned))

	for _, r := range cleaned {
		if r == '\n' {
			if keepNewlines {
				sb.WriteRune('\n')
			} else {
				sb.WriteRune(' ')
			}
		} else if r == '\t' {
			if keepNewlines {
				sb.WriteRune('\t')
			} else {
				sb.WriteRune(' ')
			}
		} else if r == ' ' {
			sb.WriteRune(' ')
		} else if r >= 32 && r <= 126 { // printable ASCII
			sb.WriteRune(r)
		} else if isHidden(r) {
			continue
		} else if unicode.Is(unicode.Zs, r) {
			sb.WriteRune(' ')
		} else if unicode.Is(unicode.Zl, r) || unicode.Is(unicode.Zp, r) {
			if keepNewlines {
				sb.WriteRune('\n')
			} else {
				sb.WriteRune(' ')
			}
		} else if unicode.Is(unicode.Cc, r) {
			if controlToSpace {
				sb.WriteRune(' ')
			}
		} else {
			sb.WriteRune(r)
		}
	}

	return sb.String()
}

// Cap truncates text if it exceeds limit, appending marker.
func Cap(text string, limit int, marker string) string {
	if limit > 0 && len(text) > limit {
		cut := limit - len(marker)
		if cut < 0 {
			cut = 0
		}
		return text[:cut] + marker
	}
	return text
}

// IsClean checks if text contains no unsanitized characters.
func IsClean(text string, keepNewlines bool) bool {
	return Scrub(text, keepNewlines, false) == text
}
