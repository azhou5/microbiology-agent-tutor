# MicroTutor V4 CSS Structure

This directory contains the CSS stylesheets for MicroTutor V4. The original monolithic `style.css` file (2318 lines) can be modularized into focused component stylesheets that align with the JavaScript modules and HTML partials.

## Current Structure

### Main Stylesheet

- **`style.css`** (2318 lines) - Complete stylesheet with all styles

### Modular Structure (Optional)

The CSS can be broken down into modular files in the `modules/` directory:

#### Core Modules (Load First)

- **`_variables.css`** - CSS custom properties (design tokens)
- **`_base.css`** - Base/reset styles, body, container
- **`_layout.css`** - Layout components (main-content, chat-container)

#### Component Modules

- **`_header.css`** - Header and footer styles
- **`_instructions.css`** - Instructions section styles
- **`_case-setup.css`** - Case setup controls (organism select, model selection)
- **`_buttons.css`** - Button component styles
- **`_guidelines.css`** - Guidelines display styles
- **`_feedback-controls.css`** - Feedback system controls
- **`_chat.css`** - Chat container and message styles
- **`_phase.css`** - Phase progression sidebar styles
- **`_dashboard.css`** - Dashboard and analytics styles
- **`_feedback-modal.css`** - Feedback modal styles
- **`_voice.css`** - Voice recording controls
- **`_mcq.css`** - Multiple Choice Question styles
- **`_audio.css`** - Audio player styles
- **`_responsive.css`** - Responsive media queries

## Should You Modularize CSS?

### ✅ **Benefits of Modularization**

1. **Maintainability**: Easier to locate and modify specific component styles
2. **Organization**: Clear separation of concerns, matches JS/HTML structure
3. **Collaboration**: Multiple developers can work on different components
4. **Reusability**: Component styles can be reused or extracted
5. **Debugging**: Easier to isolate styling issues

### ⚠️ **Considerations**

1. **Performance**: CSS `@import` statements can cause additional HTTP requests
2. **Browser Support**: `@import` is supported but not optimal for performance
3. **Build Process**: May require a CSS bundler for production

## Implementation Options

### Option 1: Keep Single File (Recommended for Now)

**Pros:**

- Single HTTP request
- No build process needed
- Better performance
- Simpler deployment

**Cons:**

- Large file (2318 lines)
- Harder to navigate
- Less modular

**When to use:** Current production setup, small team, no build process

### Option 2: Use CSS @import (Simple Modularization)

**Pros:**

- Modular structure
- No build process needed
- Easy to maintain

**Cons:**

- Multiple HTTP requests (unless HTTP/2)
- Slightly slower initial load
- Browser may block rendering until imports load

**Implementation:**

```css
/* style.css */
@import url('modules/_variables.css');
@import url('modules/_base.css');
@import url('modules/_layout.css');
/* ... etc */
```

### Option 3: Build Process (Best for Production)

**Pros:**

- Modular development
- Single optimized file for production
- Can minify and optimize
- Best performance

**Cons:**

- Requires build tool (Webpack, Vite, PostCSS, etc.)
- More complex setup
- Additional dependencies

**Tools:**

- **PostCSS** with `postcss-import`
- **Sass/SCSS** with `@use` or `@import`
- **Webpack** with CSS loaders
- **Vite** built-in CSS handling

## Recommended Approach

### For Development

Use modular CSS files for better organization and maintainability.

### For Production

1. **Option A**: Keep single `style.css` file (simplest)
2. **Option B**: Use a build process to combine modules (best performance)
3. **Option C**: Use `@import` if HTTP/2 is available (acceptable)

## Module Loading Order

If using `@import`, load modules in this order:

1. `_variables.css` - CSS variables (must load first)
2. `_base.css` - Base styles
3. `_layout.css` - Layout structure
4. `_header.css` - Header/footer
5. `_buttons.css` - Button components
6. `_instructions.css` - Instructions
7. `_case-setup.css` - Case setup
8. `_guidelines.css` - Guidelines
9. `_feedback-controls.css` - Feedback controls
10. `_chat.css` - Chat interface
11. `_phase.css` - Phase progression
12. `_dashboard.css` - Dashboard
13. `_feedback-modal.css` - Feedback modal
14. `_voice.css` - Voice controls
15. `_mcq.css` - MCQ styles
16. `_audio.css` - Audio player
17. `_responsive.css` - Responsive queries (load last)

## Alignment with Other Modules

The CSS structure aligns with:

- **JavaScript Modules**: Each CSS module corresponds to related JS functionality
- **HTML Partials**: Each CSS module styles related HTML partials
- **Component Architecture**: Clear component boundaries

## Notes

- CSS modules use underscore prefix (`_`) to indicate partials
- Original `style.css` is preserved as a backup
- All modules use CSS custom properties from `_variables.css`
- Responsive styles are separated for easier maintenance
- Component-specific styles are isolated for better organization

## Future Improvements

Potential enhancements:

- Add CSS custom properties for spacing, typography scales
- Implement CSS Grid/Flexbox utilities
- Add dark mode support via CSS variables
- Create component-specific style guides
- Add CSS linting (Stylelint)
- Implement CSS-in-JS if migrating to a framework
- Add PostCSS plugins for autoprefixing, minification

## Migration Guide

If you want to migrate to modular CSS:

1. **Backup** the current `style.css`
2. **Create** module files in `modules/` directory
3. **Extract** styles from `style.css` into appropriate modules
4. **Update** `style.css` to use `@import` statements
5. **Test** thoroughly to ensure no styles are missing
6. **Consider** a build process for production optimization

## Performance Tips

- **Minify CSS** in production
- **Use HTTP/2** if using `@import` (allows parallel requests)
- **Combine and minify** for production (single file)
- **Remove unused CSS** (PurgeCSS, uncss)
- **Use CSS custom properties** for theming
- **Optimize selectors** (avoid deep nesting)
