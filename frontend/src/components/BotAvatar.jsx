/**
 * MACE logo badge — white circular container, sharp rendering.
 * Uses /mace-logo.png (public) for full resolution without build compression.
 */

const LOGO_SRC = "/mace-logo.png";

const LOGO_PAD = 8;

/** Fixed box sizes (px) — ~25% larger than previous; 8px inner padding */
const SIZES = {
  xs: 40,
  sm: 45,
  md: 50,
  header: 60,
  lg: 70,
  xl: 90,
  launcher: 80,
};

function LogoImage({ alt }) {
  return (
    <img
      src={LOGO_SRC}
      alt={alt}
      className="mace-logo-img"
      decoding="sync"
      loading="eager"
      draggable={false}
    />
  );
}

export default function BotAvatar({
  size = "md",
  variant = "circle",
  className = "",
  alt = "MACE AI Academy logo",
}) {
  const box = SIZES[size] || SIZES.md;
  const isBadge = variant === "circle" || variant === "launcher" || variant === "card";

  if (isBadge) {
    return (
      <span
        className={`mace-logo-circle ${className}`.trim()}
        style={{ width: box, height: box, padding: LOGO_PAD }}
        title={alt}
        role="img"
        aria-label={alt}
      >
        <span className="mace-logo-frame">
          <LogoImage alt={alt} />
        </span>
      </span>
    );
  }

  return (
    <span
      className={`mace-logo-inline ${className}`.trim()}
      style={{ width: box, height: box }}
      title={alt}
      role="img"
      aria-label={alt}
    >
      <LogoImage alt={alt} />
    </span>
  );
}

export { SIZES, LOGO_PAD };
