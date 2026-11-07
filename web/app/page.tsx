import { Chat } from "@/components/Chat";

export default function Page() {
  return (
    <main className="shell">
      <header className="header">
        <h1>GatorTA</h1>
        <p>Ask about lectures, deadlines, office hours, or grading. Answers cite the slides.</p>
      </header>
      <Chat />
    </main>
  );
}
