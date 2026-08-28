export function ordinal(n: number): string {
  const rounded = Math.round(n);
  const mod100 = rounded % 100;
  if (mod100 >= 10 && mod100 <= 20) return `${rounded}th`;
  switch (rounded % 10) {
    case 1:
      return `${rounded}st`;
    case 2:
      return `${rounded}nd`;
    case 3:
      return `${rounded}rd`;
    default:
      return `${rounded}th`;
  }
}
