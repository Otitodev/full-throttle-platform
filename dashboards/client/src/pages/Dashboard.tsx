import { ActivityFeed } from "../components/ActivityFeed";
import { ApprovalCards } from "../components/ApprovalCards";
import { ClientStatsRow } from "../components/ClientStatsRow";
import { ContentList } from "../components/ContentList";
import { LeadList } from "../components/LeadList";
import { SecLabel } from "../components/ui/SecLabel";

/**
 * Owner dashboard layout.
 *
 *   < 768 px (phone): everything stacks vertically.
 *   ≥ 768 px (tablet/desktop): 2x2 card grid below the stats row.
 */
export function Dashboard() {
  return (
    <>
      <SecLabel>This Week</SecLabel>
      <ClientStatsRow />

      <div className="grid grid-cols-1 gap-4 md:grid-cols-2">
        <LeadList />
        <ApprovalCards />
      </div>

      <div className="mt-4 grid grid-cols-1 gap-4 md:grid-cols-2">
        <ContentList />
        <ActivityFeed />
      </div>
    </>
  );
}
