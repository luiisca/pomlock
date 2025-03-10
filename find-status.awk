{ print $0 }
/'"$attach_pattern"'/ {
    #print "Internal Keyboard attached"
    mode='"$mode_attached"' #kbd attached
}
/'"$detach_pattern"'/ {
    #print "Internal Keyboard detached"
    mode='"$mode_detached"' #kbd dettached
}
END {
    exit mode
}
