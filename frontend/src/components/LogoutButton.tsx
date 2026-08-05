"use client";

import { useRouter } from "next/navigation";
import { logout } from "@/lib/api-client";

export default function LogoutButton() {
  const router = useRouter();

  async function handleClick() {
    await logout();
    router.push("/login");
  }

  return (
    <button
      type="button"
      onClick={handleClick}
      className="rounded border border-gray-300 px-3 py-1.5 text-sm font-medium text-gray-700"
    >
      Sair
    </button>
  );
}
