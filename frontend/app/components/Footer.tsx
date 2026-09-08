export default function Footer() {
  return (
    <footer className="border-t border-neutral-800 mt-8">
      <div className="max-w-4xl mx-auto px-6 py-8 text-sm text-neutral-500 flex flex-wrap items-center justify-between gap-3">
        <p>Built by Aarunesh</p>
        <a
          href="https://github.com/AaruneshAP"
          target="_blank"
          rel="noopener noreferrer"
          className="hover:text-accent underline"
        >
          GitHub
        </a>
      </div>
    </footer>
  );
}
