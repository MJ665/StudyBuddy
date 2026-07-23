/* eslint-disable @typescript-eslint/no-explicit-any */
// Pure org-tree traversal helpers extracted verbatim from LDAdminDashboard.tsx
// (keeps the shell under the 800-line cap). No component state — nodes in, list out.

export const getAllGroups = (nodes: any[]): any[] => {
  let groups: any[] = [];
  nodes?.forEach(node => {
    // 1. Check if node is a Group itself
    if (node.id && !node.departments && !node.verticals && !node.batches && !node.groups) {
      // This case might only happen if the tree is flat, but we handle it just in case
    }

    // 2. Check for explicit groups array at this level
    if (node.groups && Array.isArray(node.groups)) {
      node.groups.forEach((g: any) => groups.push({ ...g, context: node.name }));
    }

    // 3. Recursive traversal through all possible container fields
    const containers = ['departments', 'verticals', 'batches'];
    containers.forEach(containerKey => {
      if (node[containerKey] && Array.isArray(node[containerKey])) {
        groups = [...groups, ...getAllGroups(node[containerKey])];
      }
    });
  });
  return groups;
};

export const findGroupInTree = (id: number, nodes: any[]): any | null => {
  for (const node of nodes) {
    if (node.groups) {
      const found = node.groups.find((g: any) => g.id === id);
      if (found) return found;
    }
    const children = node.departments || node.verticals || node.batches;
    if (children) {
      const found: any = findGroupInTree(id, children);
      if (found) return found;
    }
  }
  return null;
};

export const getAllBatches = (nodes: any[]): any[] => {
  let batches: any[] = [];
  nodes?.forEach(node => {
    if (node.batches && Array.isArray(node.batches)) {
      node.batches.forEach((b: any) => batches.push({ ...b, context: node.name }));
    }
    const containers = ['departments', 'verticals'];
    containers.forEach(containerKey => {
      if (node[containerKey] && Array.isArray(node[containerKey])) {
        batches = [...batches, ...getAllBatches(node[containerKey])];
      }
    });
  });
  return batches;
};
