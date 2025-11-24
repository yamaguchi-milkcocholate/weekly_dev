"use client";

import { useState } from "react";

export default function Home() {
  const [text, setText] = useState("");

  const handleClick = () => {
    console.log("入力値:", text);
  };

  return (
    <main className="p-6 space-y-4">
      <input className="border p-2" onChange={(e) => setText(e.target.value)} />

      <button
        className="bg-blue-600 text-white p-2 rounded"
        onClick={handleClick}
      >
        表示する
      </button>
    </main>
  );
}
