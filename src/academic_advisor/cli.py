"""Small administrative commands for the local workshop application."""

import argparse
import sys

from academic_advisor.agent.gemini import Gemini, ProviderError
from academic_advisor.config import Settings
from academic_advisor.knowledge.service import DocumentService
from academic_advisor.storage.knowledge import KnowledgeStore
from academic_advisor.storage.postgres import Database, DatabaseError


def _store(settings: Settings) -> KnowledgeStore:
    database = Database(settings)
    database.migrate()
    return KnowledgeStore(database, f"{settings.embedding_model}:{settings.embedding_dimension}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Fictional student helpdesk administration")
    parser.add_argument("command", choices=["init-db", "list-documents", "load-samples", "smoke"])
    args = parser.parse_args()
    settings = Settings()
    try:
        if args.command == "init-db":
            Database(settings).migrate()
            print("Database initialized.")
            return
        store = _store(settings)
        if args.command == "list-documents":
            documents = store.documents()
            if not documents:
                print("No indexed documents.")
            for document in documents:
                print(f"{document.filename}\t{document.passage_count} passages\t{document.content_hash[:12]}")
            return
        service = DocumentService(store, Gemini(settings), settings)
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
