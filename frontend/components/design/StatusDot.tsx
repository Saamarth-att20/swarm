// A call's status as a coloured dot. Author: Saamarth Attray
import { Icon } from "@/components/design/Icon";

export type Status = "standby" | "calling" | "talking" | "found" | "closed";

export function StatusDot({ status }: { status: Status }) {
  return (
    <span className={`status-dot ${status}`}>
      {status === "found" && <Icon name="check" size={12} />}
    </span>
  );
}