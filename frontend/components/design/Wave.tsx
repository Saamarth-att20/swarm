// Little audio bars that show a call is live. Author: Saamarth Attray
export function Wave() {
  return (
    <span className="wave" role="img" aria-label="Live audio">
      {[1, 2, 3, 4, 5].map((i) => (
        <i key={i} />
      ))}
    </span>
  );
}