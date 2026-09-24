"""Small administrative commands for the local workshop application."""

import argparse
import sys

from academic_advisor.agent.errors import ProviderError
from academic_advisor.agent.providers import create_client, select_provider
from academic_advisor.config import Settings
from academic_advisor.knowledge.service import DocumentService
from academic_advisor.storage.knowledge import KnowledgeStore
from academic_advisor.storage.postgres import Database, DatabaseError


def _store(settings: Settings, provider: str) -> KnowledgeStore:
    database = Database(settings)
    database.migrate()
    return KnowledgeStore(database, settings.signature(provider))


def main() -> None:
    parser = argparse.ArgumentParser(description="Fictional student helpdesk administration")
    parser.add_argument("command", choices=["init-db", "list-documents", "load-samples", "smoke"])
    parser.add_argument("--provider", choices=["gemini", "openai"])
    args = parser.parse_args()
    settings = Settings()
    try:
        if args.command == "init-db":
            Database(settings).migrate()
            print("Database initialized.")
            return
        provider = args.provider or settings.default_provider()
        store = _store(settings, provider)
        if args.command == "list-documents":
            documents = store.documents()
            if not documents:
                print("No indexed documents.")
            for document in documents:
                print(f"{document.filename}\t{document.passage_count} passages\t{document.content_hash[:12]}")
            return
        provider, notice, _ = select_provider(settings, provider)
        if notice:
            print(f"Using {provider}. {notice}")
        store = _store(settings, provider)
        service = DocumentService(store, create_client(settings, provider), settings.for_provider(provider))
        if args.command == "load-samples":
            loaded = 0
            for path in sorted(settings.sample_dir.iterdir()):
                if path.suffix.lower() not in {".pdf", ".txt", ".docx", ".md", ".markdown"}:
                    continue
                upload = service.preview(path.name, path.read_bytes())
                print(path.name, service.add(upload))
                loaded += 1
            print(f"Processed {loaded} fictional sample documents.")
            return
        probe = service.search("What information is available in the knowledge base?")
        print(f"Knowledge search is healthy; returned {len(probe)} passages.")
    except (OSError, ValueError, ProviderError, DatabaseError) as error:
        print(str(error), file=sys.stderr)
        raise SystemExit(1) from None


if __name__ == "__main__":
    main()
