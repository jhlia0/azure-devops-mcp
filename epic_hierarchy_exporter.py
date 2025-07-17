#!/usr/bin/env python3
"""
Epic Hierarchy Exporter

This script reads all work items under a specified Epic and organizes them into a
hierarchical structure, then outputs the content in markdown format.

Hierarchy: Epic -> Features -> User Stories -> Tasks/Bugs
"""

import asyncio
import argparse
import sys
from typing import Dict, List, Any, Optional
from src.client import AzureDevOpsClient, WorkItem
from config import settings


class EpicHierarchyExporter:
    """Exports Epic hierarchy to markdown format."""

    def __init__(self):
        self.client = AzureDevOpsClient()
        self.hierarchy = {}

    async def get_epic_hierarchy(self, epic_id: int) -> Dict[str, Any]:
        """Get complete Epic hierarchy including Features, User Stories, Tasks, and Bugs."""

        # Step 1: Get the Epic itself
        epic_items = await self.client.get_work_items([epic_id])
        if not epic_items:
            raise ValueError(f"Epic with ID {epic_id} not found")

        epic = epic_items[0]
        if epic.work_item_type != "Epic":
            raise ValueError(
                f"Work item {epic_id} is not an Epic (type: {epic.work_item_type})"
            )

        # Step 2: Get all Features under this Epic
        features = await self._get_children_by_type(epic_id, "Feature")

        # Step 3: Build proper hierarchy with parent-child relationships
        feature_hierarchy = []
        for feature in features:
            # Get User Stories under this Feature
            user_stories = await self._get_children_by_type(feature.id, "User Story")

            user_story_hierarchy = []
            for user_story in user_stories:
                # Get Tasks and Bugs under this User Story
                tasks = await self._get_children_by_type(user_story.id, "Task")
                bugs = await self._get_children_by_type(user_story.id, "Bug")

                user_story_hierarchy.append(
                    {"work_item": user_story, "tasks": tasks, "bugs": bugs}
                )

            feature_hierarchy.append(
                {"work_item": feature, "user_stories": user_story_hierarchy}
            )

        hierarchy = {"epic": epic, "features": feature_hierarchy}

        return hierarchy

    async def _get_children_by_type(
        self, parent_id: int, work_item_type: str
    ) -> List[WorkItem]:
        """Get child work items of specific type using WIQL."""
        wiql = f"""
        SELECT [System.Id]
        FROM WorkItemLinks
        WHERE [Source].[System.Id] = {parent_id}
        AND [Target].[System.WorkItemType] = '{work_item_type}'
        AND [System.Links.LinkType] = 'System.LinkTypes.Hierarchy-Forward'
        MODE (MustContain)
        """

        try:
            # Use execute_wiql to get the raw response with work item relations
            data = await self.client.execute_wiql(wiql)

            # Extract work item relations and get target IDs
            work_item_relations = data.get("workItemRelations", [])
            if not work_item_relations:
                return []

            # Get target IDs (children)
            target_ids = []
            for relation in work_item_relations:
                if relation.get("target") and relation.get("target", {}).get("id"):
                    target_ids.append(relation["target"]["id"])

            if not target_ids:
                return []

            # Get full work item details
            return await self.client.get_work_items(target_ids)

        except Exception as e:
            print(f"Error getting {work_item_type} children for {parent_id}: {e}")
            return []

    def generate_markdown(self, hierarchy: Dict[str, Any]) -> str:
        """Generate markdown output from hierarchy."""
        epic = hierarchy["epic"]
        features = hierarchy["features"]

        md_lines = []

        # Epic header
        md_lines.append(f"# Epic: {epic.title}")
        md_lines.append(f"**ID:** {epic.id}")
        md_lines.append(f"**State:** {epic.state}")
        md_lines.append(f"**Assigned To:** {epic.assigned_to or 'Unassigned'}")
        md_lines.append(f"**Created:** {epic.created_date}")
        if epic.description:
            md_lines.append(f"**Description:** {epic.description}")
        md_lines.append("")

        # Features
        for i, feature_data in enumerate(features, 1):
            feature = feature_data["work_item"]
            user_stories = feature_data["user_stories"]

            md_lines.append(f"## {i}. Feature: {feature.title}")
            md_lines.append(f"**ID:** {feature.id}")
            md_lines.append(f"**State:** {feature.state}")
            md_lines.append(f"**Assigned To:** {feature.assigned_to or 'Unassigned'}")
            if feature.description:
                md_lines.append(f"**Description:** {feature.description}")
            md_lines.append("")

            # User Stories
            if user_stories:
                for j, us_data in enumerate(user_stories, 1):
                    user_story = us_data["work_item"]
                    tasks = us_data["tasks"]
                    bugs = us_data["bugs"]

                    md_lines.append(f"### {i}.{j} User Story: {user_story.title}")
                    md_lines.append(f"**ID:** {user_story.id}")
                    md_lines.append(f"**State:** {user_story.state}")
                    md_lines.append(
                        f"**Assigned To:** {user_story.assigned_to or 'Unassigned'}"
                    )
                    if user_story.description:
                        md_lines.append(f"**Description:** {user_story.description}")
                    md_lines.append("")

                    # Tasks
                    if tasks:
                        md_lines.append("#### Tasks:")
                        for k, task in enumerate(tasks, 1):
                            md_lines.append(f"- **{i}.{j}.T{k} Task:** {task.title}")
                            md_lines.append(f"  - **ID:** {task.id}")
                            md_lines.append(f"  - **State:** {task.state}")
                            md_lines.append(
                                f"  - **Assigned To:** {task.assigned_to or 'Unassigned'}"
                            )
                        md_lines.append("")

                    # Bugs
                    if bugs:
                        md_lines.append("#### Bugs:")
                        for k, bug in enumerate(bugs, 1):
                            md_lines.append(f"- **{i}.{j}.B{k} Bug:** {bug.title}")
                            md_lines.append(f"  - **ID:** {bug.id}")
                            md_lines.append(f"  - **State:** {bug.state}")
                            md_lines.append(
                                f"  - **Assigned To:** {bug.assigned_to or 'Unassigned'}"
                            )
                        md_lines.append("")
            else:
                md_lines.append("*No User Stories found for this Feature*")
                md_lines.append("")

        return "\n".join(md_lines)


async def main():
    """Main execution function."""
    parser = argparse.ArgumentParser(description="Export Epic hierarchy to markdown")
    parser.add_argument("epic_id", type=int, help="Epic ID to export")
    parser.add_argument("-o", "--output", help="Output file path (default: stdout)")

    args = parser.parse_args()

    try:
        exporter = EpicHierarchyExporter()

        print(f"Fetching hierarchy for Epic {args.epic_id}...")
        hierarchy = await exporter.get_epic_hierarchy(args.epic_id)

        print("Generating markdown...")
        markdown_content = exporter.generate_markdown(hierarchy)

        if args.output:
            with open(args.output, "w", encoding="utf-8") as f:
                f.write(markdown_content)
            print(f"Output written to {args.output}")
        else:
            print("\n" + "=" * 50)
            print(markdown_content)

    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())
