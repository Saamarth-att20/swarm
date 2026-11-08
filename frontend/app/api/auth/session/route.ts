
import { NextResponse } from "next/server";
import { auth0 } from "@/lib/auth0";

export async function GET() {
    try {
        const session = await auth0.getSession();

        if (!session?.user) {
            return NextResponse.json(null);
        }

        const user = session.user;

        return NextResponse.json({
            id: user.sub,
            name: user.name ?? user.nickname ?? user.email ?? "User",
            email: user.email ?? "",
        });
    } catch {
        return NextResponse.json(
            { error: "Unable to retrieve session" },
            { status: 500 }
        );
    }
}
