const REPO = "https://github.com/namyaa6/CollectionsLab";

export default function Footer() {
  return (
    <footer className="footer">
      <div className="footer-inner">
        <nav aria-label="Project links">
          <a href={REPO}>GitHub repo</a>
          <a href={`${REPO}#how-it-works`}>Methodology (README)</a>
          <a href={`${REPO}#demo`}>Demo video</a>
        </nav>
        <p>
          Synthetic data only; <a href={`${REPO}#limitations`}>limitations in the README</a>.
        </p>
      </div>
    </footer>
  );
}
