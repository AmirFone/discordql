"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { UserButton } from "@clerk/nextjs";

const navItems = [
  { href: "/dashboard", label: "Overview", icon: "📊" },
  { href: "/dashboard/bot", label: "Bot Config", icon: "🤖" },
  { href: "/dashboard/query", label: "SQL Editor", icon: "⚡" },
  { href: "/dashboard/settings", label: "Settings", icon: "⚙️" },
];

export default function DashboardLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  const pathname = usePathname();

  return (
    <div className="min-h-screen bg-gray-900 text-white flex">
      {/* Sidebar */}
      <aside className="w-64 bg-gray-800 border-r border-gray-700 flex flex-col">
        <div className="p-6 border-b border-gray-700">
          <Link href="/" className="text-xl font-bold text-indigo-400">
            Discord Analytics
          </Link>
        </div>

        <nav className="flex-1 p-4">
          <ul className="space-y-2">
            {navItems.map((item) => (
              <li key={item.href}>
                <Link
                  href={item.href}
                  className={`flex items-center gap-3 px-4 py-3 rounded-lg transition ${
                    pathname === item.href
                      ? "bg-indigo-600 text-white"
                      : "text-gray-300 hover:bg-gray-700"
                  }`}
                >
                  <span>{item.icon}</span>
                  <span>{item.label}</span>
                </Link>
              </li>
            ))}
          </ul>
        </nav>

        <div className="p-4 border-t border-gray-700">
          <div className="flex items-center gap-3">
            <UserButton afterSignOutUrl="/" />
            <span className="text-sm text-gray-400">Account</span>
          </div>
        </div>
      </aside>

      {/* Main content */}
      <main className="flex-1 p-8">{children}</main>
    </div>
  );
}
