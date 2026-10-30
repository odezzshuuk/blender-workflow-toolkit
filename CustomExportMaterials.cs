#if TOOLS
using Godot;
using System;
using System.Collections.Generic;
using System.Text.RegularExpressions;

/// <summary>
/// Assign to a model's Import > Import Script > Path in a Godot .NET project.
/// Extracts materials once, then reuses them so Godot edits survive reimport.
/// </summary>
[Tool]
public partial class CustomExportMaterials : EditorScenePostImport
{
    public override GodotObject _PostImport(Node scene)
    {
        string source = GetSourceFile();
        string sourceDirectory = source.GetBaseDir();
        // Match models/<prefix>/ while retaining compatibility with older exports.
        string outputDirectory = sourceDirectory.GetBaseDir().GetFile() == "models"
            ? sourceDirectory.GetBaseDir().GetBaseDir()
            : sourceDirectory.GetFile() == "meshes"
            ? sourceDirectory.GetBaseDir()
            : sourceDirectory;
        string materialDirectory = outputDirectory.PathJoin("materials");
        Error error = DirAccess.MakeDirRecursiveAbsolute(materialDirectory);

        if (error != Error.Ok)
        {
            GD.PushError($"Cannot create material directory '{materialDirectory}': {error}");
            return scene;
        }

        // Track shared materials while extracting resources throughout the imported scene.
        var materials = new Dictionary<ulong, Material>();
        var names = new HashSet<string>(StringComparer.OrdinalIgnoreCase);
        Visit(scene, materialDirectory, materials, names);
        return scene;
    }

    private static void Visit(Node node, string directory,
        Dictionary<ulong, Material> materials, HashSet<string> names)
    {
        if (node is MeshInstance3D instance)
        {
            if (instance.MaterialOverride != null)
                instance.MaterialOverride = Extract(instance.MaterialOverride, directory, materials, names);
            if (instance.MaterialOverlay != null)
                instance.MaterialOverlay = Extract(instance.MaterialOverlay, directory, materials, names);

            Mesh mesh = instance.Mesh;
            if (mesh != null)
            {

                // Replace surface materials and overrides with reusable external resources.
                for (int surface = 0; surface < mesh.GetSurfaceCount(); surface++)
                {
                    Material material = mesh.SurfaceGetMaterial(surface);
                    if (material != null)
                        mesh.SurfaceSetMaterial(surface, Extract(material, directory, materials, names));

                    Material surfaceOverride = instance.GetSurfaceOverrideMaterial(surface);
                    if (surfaceOverride != null)
                        instance.SetSurfaceOverrideMaterial(surface,
                            Extract(surfaceOverride, directory, materials, names));
                }
            }
        }

        // Process nested meshes throughout the scene hierarchy.
        foreach (Node child in node.GetChildren())
            Visit(child, directory, materials, names);
    }

    private static Material Extract(Material material, string directory,
        Dictionary<ulong, Material> materials, HashSet<string> names)
    {
        ulong id = material.GetInstanceId();

        if (materials.TryGetValue(id, out Material cached))
            return cached;

        // Leave resources that are already external alone (including user overrides).
        if (material.ResourcePath.StartsWith("res://", StringComparison.Ordinal)
            && !material.ResourcePath.Contains("::"))
        {
            materials[id] = material;
            return material;
        }

        // Derive a safe material filename and its grouping directory.
        string stem = Regex.Replace(material.ResourceName, "[^A-Za-z0-9_-]", "_");
        if (string.IsNullOrEmpty(stem))
            stem = "Material";
        string prefix = stem.Split('_')[0];
        if (string.IsNullOrEmpty(prefix))
            prefix = "Material";
        string groupDirectory = directory.PathJoin(prefix);
        Error directoryError = DirAccess.MakeDirRecursiveAbsolute(groupDirectory);

        if (directoryError != Error.Ok)
        {
            GD.PushError($"Cannot create material directory '{groupDirectory}': {directoryError}; keeping the imported material.");
            materials[id] = material;
            return material;
        }

        // Reserve names in traversal order, independent of files from earlier imports.
        string name = stem;
        for (int suffix = 2; !names.Add(name); suffix++)
            name = $"{stem}_{suffix}";
        string path = groupDirectory.PathJoin(name + ".tres");

        // Reuse an existing external material so edits survive reimport.
        Material external;
        if (FileAccess.FileExists(path))
        {
            external = ResourceLoader.Load<Material>(path);

            if (external == null)
            {
                GD.PushError($"Cannot load material '{path}'; keeping the imported material.");
                materials[id] = material;
                return material;
            }
        }
        else
        {
            // Shallow duplication keeps external texture references intact.
            external = (Material)material.Duplicate();
            Error error = ResourceSaver.Save(external, path);

            if (error != Error.Ok)
            {
                GD.PushError($"Cannot save material '{path}': {error}; keeping the imported material.");
                materials[id] = material;
                return material;
            }

            // Give the replacement a persistent external reference for scene packing.
            external.ResourcePath = path;
        }

        // Cache both identities so shared references use the same external resource.
        materials[id] = external;
        materials[external.GetInstanceId()] = external;
        return external;
    }
}
#endif
