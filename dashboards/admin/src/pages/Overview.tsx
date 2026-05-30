import { ApprovalQueue } from "../components/ApprovalQueue";
import { AuditTrail } from "../components/AuditTrail";
import { ClientTable } from "../components/ClientTable";
import { StatsRow } from "../components/StatsRow";
import { SecLabel } from "../components/ui/SecLabel";

export function Overview() {
  return (
    <>
      <SecLabel>Platform Overview</SecLabel>
      <StatsRow />

      <div className="grid grid-cols-1 gap-4 lg:grid-cols-[2fr_1fr]">
        <ClientTable />
        <div className="flex flex-col gap-4">
          <ApprovalQueue />
          <AuditTrail />
        </div>
      </div>
    </>
  );
}
