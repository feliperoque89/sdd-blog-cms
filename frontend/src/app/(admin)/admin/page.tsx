import LogoutButton from "@/components/LogoutButton";

export default function AdminDashboardPage() {
  return (
    <div className="flex items-center justify-between">
      <h1 className="text-xl font-semibold">Painel administrativo</h1>
      <LogoutButton />
    </div>
  );
}
