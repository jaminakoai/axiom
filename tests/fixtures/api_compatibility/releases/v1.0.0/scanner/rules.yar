rule AxiomCompatMarker {
    strings:
        $marker = "AXIOM_COMPAT_MARKER"
    condition:
        $marker
}
