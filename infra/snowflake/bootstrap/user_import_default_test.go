package resources

import (
	"context"
	"testing"

	"github.com/Snowflake-Labs/terraform-provider-snowflake/pkg/internal/provider"
	"github.com/Snowflake-Labs/terraform-provider-snowflake/pkg/sdk"
	"github.com/hashicorp/terraform-plugin-sdk/v2/helper/schema"
	"github.com/stretchr/testify/require"
)

// Unimplemented (including mutation) methods panic if import attempts to call them.
type userImportFixture struct {
	sdk.Users
	describes int
	shows     int
}

func (f *userImportFixture) DescribeDetails(_ context.Context, id sdk.AccountObjectIdentifier) (*sdk.UserDetails, error) {
	f.describes++
	return &sdk.UserDetails{
		LoginName:          &sdk.StringProperty{Value: id.Name()},
		DisplayName:        &sdk.StringProperty{Value: id.Name()},
		DefaultNamespace:   &sdk.StringProperty{},
		Disabled:           &sdk.BoolProperty{},
		MustChangePassword: &sdk.BoolProperty{},
	}, nil
}

func (f *userImportFixture) ShowByID(_ context.Context, id sdk.AccountObjectIdentifier) (*sdk.User, error) {
	f.shows++
	return &sdk.User{Name: id.Name(), DefaultSecondaryRoles: `["ALL"]`}, nil
}

func TestImportUserPreservesLockTimerDefault(t *testing.T) {
	for _, kind := range []sdk.UserType{sdk.UserTypeService, sdk.UserTypePerson, sdk.UserTypeLegacyService} {
		t.Run(string(kind), func(t *testing.T) {
			resource := ServiceUser()
			if kind == sdk.UserTypePerson {
				resource = User()
			} else if kind == sdk.UserTypeLegacyService {
				resource = LegacyServiceUser()
			}
			data := schema.TestResourceDataRaw(t, resource.Schema, map[string]interface{}{"name": "EXISTING_USER"})
			require.NoError(t, data.Set("mins_to_unlock", nil))
			data.SetId(`"EXISTING_USER"`)
			fixture := &userImportFixture{}
			result, err := GetImportUserFunc(kind)(context.Background(), data, &provider.Context{Client: &sdk.Client{Users: fixture}})
			require.NoError(t, err)
			require.Len(t, result, 1)
			require.Equal(t, IntDefault, result[0].Get("mins_to_unlock"))
			require.Equal(t, 1, fixture.describes)
			require.Equal(t, 1, fixture.shows)
		})
	}
}
