# Typography Guidelines - BuildIQ

## Font System

BuildIQ uses **Figtree** as the primary font family with system font fallbacks for optimal performance and cross-platform compatibility.

## Font Size Scale

Our typography system uses a consistent scale based on rem units:

| Name | CSS Variable | Size (rem) | Size (px) | Usage |
|------|-------------|-----------|-----------|--------|
| XS   | `--text-xs` | 0.75rem | 12px | Captions, metadata, fine print |
| SM   | `--text-sm` | 0.875rem | 14px | Labels, buttons, table text |
| Base | `--text-base` | 1rem | 16px | Body text, form inputs |
| LG   | `--text-lg` | 1.125rem | 18px | Large body text, small headings |
| XL   | `--text-xl` | 1.25rem | 20px | Component headings |
| 2XL  | `--text-2xl` | 1.5rem | 24px | Card titles, section headings |
| 3XL  | `--text-3xl` | 1.875rem | 30px | Page section headings |
| 4XL  | `--text-4xl` | 2.25rem | 36px | Page titles, major headings |
| 5XL  | `--text-5xl` | 3rem | 48px | Display headings, hero text |

## Semantic Typography Classes

Use these utility classes for consistent styling:

### Display & Headings
- `.text-display` - Hero text, landing page headlines (48px, medium weight)
- `.text-headline` - Page titles, major headings (36px, medium weight)
- `.text-title` - Section headings (30px, medium weight)
- `.text-subtitle` - Subsection headings, card titles (24px, medium weight)

### Body Text
- `.text-body-large` - Emphasis body text, introductions (18px, normal weight)
- `.text-body` - Standard body text, descriptions (16px, normal weight)
- `.text-body-small` - Supporting text, table content (14px, normal weight)

### Labels & UI Elements
- `.text-label-large` - Important form labels, button text (16px, medium weight)
- `.text-label` - Standard labels, navigation items (14px, medium weight)
- `.text-label-small` - Secondary labels, badges (12px, medium weight)

### Captions & Metadata
- `.text-caption` - Timestamps, metadata, helper text (12px, normal weight)

## Default Element Styling

Our base layer provides consistent styling for HTML elements:

- **h1**: Display/headline level (36px, medium, tight line-height)
- **h2**: Title level (30px, medium)
- **h3**: Subtitle level (24px, medium)
- **h4**: Component heading level (20px, medium)
- **h5**: Small heading level (18px, medium)
- **h6**: Micro heading level (16px, medium)
- **p**: Body text (16px, normal, comfortable line-height)
- **button**: Interface elements (14px, medium)
- **label**: Form labels (14px, medium)
- **input/textarea**: Form inputs (14px, normal)
- **small**: Fine print (12px, normal)

## Line Heights

- **1.1**: Display text and large headings (tight)
- **1.2-1.4**: Headings and titles (comfortable)
- **1.5**: Interface elements and labels (standard)
- **1.6**: Body text and paragraphs (readable)

## Letter Spacing

- **-0.03em**: Display text (5XL)
- **-0.02em**: Headlines (4XL)
- **-0.01em**: Titles (3XL)
- **0**: Standard text (2XL and below)

## Font Weights

- **400 (normal)**: Body text, descriptions, form inputs
- **500 (medium)**: Headings, labels, buttons, emphasis

## Usage Guidelines

### DO:
- Use semantic typography classes (`.text-headline`, `.text-body`) for consistent styling
- Follow the established hierarchy (h1 > h2 > h3, etc.)
- Use appropriate line-heights for text length and context
- Maintain consistent spacing between typography elements

### DON'T:
- Use arbitrary font sizes outside the established scale
- Override font sizes with inline styles or custom CSS
- Use font weights other than 400 and 500 without design approval
- Mix different typography patterns in similar UI contexts

## Responsive Considerations

The typography system uses rem units which scale with the root font size (16px). For mobile optimization:

- Consider using smaller headings levels on mobile (h2 instead of h1)
- Ensure sufficient line-height for touch interfaces
- Maintain readability at different screen sizes

## Implementation

Always prefer using the CSS custom properties and utility classes:

```css
/* Good */
.page-title {
  font-size: var(--text-4xl);
  font-weight: var(--font-weight-medium);
}

/* Better */
.page-title {
  @apply text-headline;
}

/* Best */
<h1 class="text-headline">Page Title</h1>
```

This ensures consistency and makes it easy to update typography system-wide.